"""Download and verify official global crop rasters into a persistent data directory.

Large source files stay on disk. This script never loads raster arrays into RAM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path

from .global_raster_catalog import CROPGRIDS, MAPSPAM, mapspam_cog_assets


def stream_download(url: str, destination: Path, expected_size: int | None = None,
                    expected_md5: str | None = None, timeout: int = 90) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        size = destination.stat().st_size
        if expected_size is None or size == expected_size:
            if expected_md5 is None or _md5(destination) == expected_md5:
                return {"path": str(destination), "bytes": size, "cached": True}
    fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".part",
                                     dir=destination.parent)
    os.close(fd)
    temp = Path(temp_name)
    digest = hashlib.md5()
    size = 0
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "OSH-Agriculture-AI/0.1"})
        with urllib.request.urlopen(request, timeout=timeout) as response, temp.open("wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                size += len(chunk)
        if expected_size is not None and size != expected_size:
            raise ValueError(f"Size mismatch: expected {expected_size}, received {size}")
        actual_md5 = digest.hexdigest()
        if expected_md5 and actual_md5.lower() != expected_md5.lower():
            raise ValueError(f"MD5 mismatch: expected {expected_md5}, received {actual_md5}")
        os.replace(temp, destination)
        return {"path": str(destination), "bytes": size, "md5": actual_md5, "cached": False}
    except Exception:
        temp.unlink(missing_ok=True)
        raise


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sync_mapspam(data_root: Path, assets: list[str] | None = None) -> list[dict]:
    wanted = set(assets or [])
    results = []
    for asset in mapspam_cog_assets():
        if asset["asset_id"] == "crop-codes" or (wanted and asset["asset_id"] not in wanted):
            continue
        dest = data_root / "mapspam-2020-v2r2" / asset["filename"]
        result = stream_download(asset["url"], dest)
        result.update({"dataset_id": MAPSPAM["dataset_id"], "asset_id": asset["asset_id"]})
        results.append(result)
    # Always fetch the published crop-code metadata for band interpretation.
    meta = next(x for x in mapspam_cog_assets() if x["asset_id"] == "crop-codes")
    result = stream_download(meta["url"], data_root / "mapspam-2020-v2r2" / meta["filename"])
    result.update({"dataset_id": MAPSPAM["dataset_id"], "asset_id": "crop-codes"})
    results.append(result)
    return results


def sync_cropgrids(data_root: Path) -> dict:
    dest = data_root / CROPGRIDS["dataset_id"] / CROPGRIDS["filename"]
    result = stream_download(CROPGRIDS["url"], dest,
                             CROPGRIDS["expected_size_bytes"],
                             CROPGRIDS["expected_md5"])
    result.update({"dataset_id": CROPGRIDS["dataset_id"]})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync official global crop raster data")
    parser.add_argument("--data-dir", type=Path,
                        default=Path(os.environ.get("OSH_AGRI_DATA_DIR", "data/global")))
    parser.add_argument("--dataset", choices=["mapspam", "cropgrids", "both"], default="mapspam")
    parser.add_argument("--assets", nargs="*", help="MAPSPAM asset IDs; default downloads all 12 COGs")
    args = parser.parse_args()
    results = []
    if args.dataset in {"mapspam", "both"}:
        results.extend(sync_mapspam(args.data_dir, args.assets))
    if args.dataset in {"cropgrids", "both"}:
        results.append(sync_cropgrids(args.data_dir))
    print(json.dumps({"data_dir": str(args.data_dir.resolve()), "downloads": results},
                     indent=2))


if __name__ == "__main__":
    main()
