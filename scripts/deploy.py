from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable
import zipfile


REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "dist"
ARCHIVE_NAME = "football_app_release.zip"
ARCHIVE_PATH = DIST_DIR / ARCHIVE_NAME


def run_tests() -> None:
    """Run the pytest suite before packaging."""
    print(">> Running pytest to validate the project...")
    subprocess.check_call([sys.executable, "-m", "pytest"], cwd=REPO_ROOT)


def iter_files(paths: Iterable[str]) -> Iterable[Path]:
    for raw in paths:
        path = (REPO_ROOT / raw).resolve()
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and "__pycache__" not in child.parts:
                    yield child


def build_archive() -> None:
    """Create a deployment zip with the core application files."""
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    include_paths = [
        "app.py",
        "requirements.txt",
        "README.md",
        "utils",
        "assets",
        "scripts",
    ]

    print(f">> Building archive at {ARCHIVE_PATH} ...")
    with zipfile.ZipFile(ARCHIVE_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in iter_files(include_paths):
            arcname = file_path.relative_to(REPO_ROOT)
            zf.write(file_path, arcname)

    print(f">> Done. Archive available at {ARCHIVE_PATH}")


def main() -> None:
    run_tests()
    build_archive()


if __name__ == "__main__":
    main()
