"""Download and validate official global crop raster datasets.

Large source files stay on disk. Downloads are streamed to a same-filesystem
temporary file and atomically renamed only after size/hash checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path

from .global_raster_catalog import (
    CROPGRIDS,
    MAPSPAM,
    default_global_data_dir,
    mapspam_cog_assets,
)


MAPSPAM_CORE_ASSETS = {
    "physical_area-all",
    "harvested_area-all",
    "production-all",
    "yield-all",
}


def stream_download(
    url: str,
    destination: Path,
    expected_size: int | None = None,
    expected_md5: str | None = None,
    timeout: int = 90,
) -> dict:
    """Stream one file and replace the destination only after validation."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        size = destination.stat().st_size
        size_ok = expected_size is None or size == expected_size
        hash_ok = expected_md5 is None or _md5(destination) == expected_md5
        if size_ok and hash_ok:
            return {"path": str(destination), "bytes": size, "cached": True}

    fd, temp_name = tempfile.mkstemp(
        prefix=destination.name + ".", suffix=".part", dir=destination.parent
    )
    os.close(fd)
    temp = Path(temp_name)
    digest = hashlib.md5()
    size = 0
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "OSH-Agriculture-AI/0.2"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_length = response.headers.get("Content-Length")
            expected_response_size = int(content_length) if content_length else None
            with temp.open("wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)

        if expected_size is not None and size != expected_size:
            raise ValueError(
                f"Size mismatch: expected {expected_size}, received {size}"
            )
        if expected_response_size is not None and size != expected_response_size:
            raise ValueError(
                f"HTTP Content-Length mismatch: expected {expected_response_size}, received {size}"
            )
        actual_md5 = digest.hexdigest()
        if expected_md5 and actual_md5.lower() != expected_md5.lower():
            raise ValueError(
                f"MD5 mismatch: expected {expected_md5}, received {actual_md5}"
            )
        os.replace(temp, destination)
        return {
            "path": str(destination),
            "bytes": size,
            "md5": actual_md5,
            "cached": False,
        }
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_mapspam_cog(path: Path) -> dict:
    """Validate a downloaded MAPSPAM COG before marking it usable."""
    try:
        import rasterio
    except ImportError as exc:
        raise RuntimeError("MAPSPAM COG validation requires rasterio>=1.5") from exc

    with rasterio.open(path) as dataset:
        if dataset.count != MAPSPAM["crop_count"]:
            raise ValueError(
                f"{path.name}: expected 46 crop bands, got {dataset.count}"
            )
        if dataset.crs is None or dataset.crs.to_epsg() != 4326:
            raise ValueError(f"{path.name}: expected EPSG:4326, got {dataset.crs}")
        if dataset.width <= 0 or dataset.height <= 0:
            raise ValueError(f"{path.name}: invalid raster dimensions")
        return {
            "width": dataset.width,
            "height": dataset.height,
            "bands": dataset.count,
            "crs": dataset.crs.to_string(),
            "nodata": dataset.nodata,
        }


def sync_mapspam(
    data_root: Path,
    assets: list[str] | None = None,
    all_technologies: bool = False,
) -> list[dict]:
    """Download the 4 all-technology core layers by default.

    Pass --all-technologies to additionally download irrigated and rainfed
    disaggregations (12 GeoTIFFs total).
    """
    if assets is not None:
        wanted = set(assets)
    elif all_technologies:
        wanted = {
            asset["asset_id"]
            for asset in mapspam_cog_assets()
            if asset["asset_id"] != "crop-codes"
        }
    else:
        wanted = set(MAPSPAM_CORE_ASSETS)

    known = {
        asset["asset_id"]
        for asset in mapspam_cog_assets()
        if asset["asset_id"] != "crop-codes"
    }
    unknown = wanted - known
    if unknown:
        raise ValueError(f"Unknown MAPSPAM asset IDs: {sorted(unknown)}")

    results = []
    dataset_dir = data_root / MAPSPAM["dataset_id"]
    for asset in mapspam_cog_assets():
        asset_id = asset["asset_id"]
        if asset_id == "crop-codes" or asset_id not in wanted:
            continue
        destination = dataset_dir / asset["filename"]
        result = stream_download(asset["url"], destination)
        try:
            raster_info = validate_mapspam_cog(destination)
        except Exception:
            # A cached but invalid TIFF must not be silently reused.
            destination.unlink(missing_ok=True)
            result = stream_download(asset["url"], destination)
            raster_info = validate_mapspam_cog(destination)
        result.update({
            "dataset_id": MAPSPAM["dataset_id"],
            "asset_id": asset_id,
            "raster": raster_info,
        })
        results.append(result)

    metadata_asset = next(
        asset for asset in mapspam_cog_assets()
        if asset["asset_id"] == "crop-codes"
    )
    metadata_path = dataset_dir / metadata_asset["filename"]
    metadata_result = stream_download(metadata_asset["url"], metadata_path)
    try:
        metadata_json = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata_result["metadata_valid_json"] = isinstance(metadata_json, (dict, list))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        metadata_path.unlink(missing_ok=True)
        raise ValueError("MAPSPAM crop-codes.json is not valid JSON") from exc
    metadata_result.update({
        "dataset_id": MAPSPAM["dataset_id"],
        "asset_id": "crop-codes",
    })
    results.append(metadata_result)
    return results


def sync_cropgrids(data_root: Path) -> dict:
    destination = data_root / CROPGRIDS["dataset_id"] / CROPGRIDS["filename"]
    result = stream_download(
        CROPGRIDS["url"],
        destination,
        CROPGRIDS["expected_size_bytes"],
        CROPGRIDS["expected_md5"],
    )
    result.update({
        "dataset_id": CROPGRIDS["dataset_id"],
        "license": CROPGRIDS["license"],
        "reference_year": CROPGRIDS["reference_year"],
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync official global crop raster data"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=default_global_data_dir(),
    )
    parser.add_argument(
        "--dataset",
        choices=["mapspam", "cropgrids", "both"],
        default="mapspam",
    )
    parser.add_argument(
        "--assets",
        nargs="*",
        help="Explicit MAPSPAM asset IDs (e.g. yield-all)",
    )
    parser.add_argument(
        "--all-technologies",
        action="store_true",
        help="Download all 12 MAPSPAM COGs instead of the 4 core all-technology COGs",
    )
    args = parser.parse_args()

    results = []
    if args.dataset in {"mapspam", "both"}:
        results.extend(
            sync_mapspam(
                args.data_dir,
                assets=args.assets,
                all_technologies=args.all_technologies,
            )
        )
    if args.dataset in {"cropgrids", "both"}:
        results.append(sync_cropgrids(args.data_dir))

    print(json.dumps({
        "data_dir": str(args.data_dir.resolve()),
        "downloads": results,
        "downloaded_bytes": sum(int(item.get("bytes", 0)) for item in results),
    }, indent=2))


if __name__ == "__main__":
    main()
