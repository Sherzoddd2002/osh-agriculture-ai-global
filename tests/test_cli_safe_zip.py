import stat
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = ROOT / "bin" / "safe_extract_zip.py"


def _run_extractor(archive: Path, destination: Path):
    return subprocess.run(
        [sys.executable, str(EXTRACTOR), str(archive), str(destination)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def test_safe_extractor_unpacks_normal_github_source_zip(tmp_path):
    archive = tmp_path / "source.zip"
    destination = tmp_path / "unpack"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("osh-agriculture-ai-global-main/", "")
        zf.writestr(
            "osh-agriculture-ai-global-main/requirements.txt",
            "fastapi\n",
        )
        zf.writestr(
            "osh-agriculture-ai-global-main/backend/app/main.py",
            "app = object()\n",
        )
        zf.writestr(
            "osh-agriculture-ai-global-main/frontend/index.html",
            "<html></html>",
        )

    result = _run_extractor(archive, destination)

    assert result.returncode == 0, result.stderr
    assert "safely" in result.stdout.lower()
    root = destination / "osh-agriculture-ai-global-main"
    assert (root / "requirements.txt").read_text(encoding="utf-8") == "fastapi\n"
    assert (root / "backend/app/main.py").is_file()
    assert (root / "frontend/index.html").is_file()


def test_safe_extractor_rejects_parent_directory_traversal(tmp_path):
    archive = tmp_path / "traversal.zip"
    destination = tmp_path / "unpack"
    outside = tmp_path / "outside.txt"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("repo/requirements.txt", "fastapi\n")
        zf.writestr("../outside.txt", "owned")

    result = _run_extractor(archive, destination)

    assert result.returncode != 0
    assert "Unsafe ZIP path" in result.stderr
    assert not outside.exists()


def test_safe_extractor_rejects_windows_drive_paths(tmp_path):
    archive = tmp_path / "drive.zip"
    destination = tmp_path / "unpack"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("C:/outside.txt", "owned")

    result = _run_extractor(archive, destination)

    assert result.returncode != 0
    assert "Absolute ZIP path" in result.stderr


def test_safe_extractor_rejects_symlink_entries(tmp_path):
    archive = tmp_path / "symlink.zip"
    destination = tmp_path / "unpack"
    outside = tmp_path / "outside.txt"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("repo/requirements.txt", "fastapi\n")
        link = zipfile.ZipInfo("repo/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(link, str(outside))

    result = _run_extractor(archive, destination)

    assert result.returncode != 0
    assert "Symlink entries are not allowed" in result.stderr
    assert not outside.exists()
