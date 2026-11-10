"""Build script to package the Python gear_reduction package for client-side Pyodide execution.

Engineering Rationale:
---------------------
Pyodide runs inside a browser WebAssembly virtual environment. Packaging `src/gear_reduction`
into a zip archive (`web/python/gear_reduction.zip`) allows the browser Web Worker to download
a single lightweight archive (~25 KB) and unpack it directly into Pyodide's virtual filesystem
using `pyodide.unpackArchive()`. This guarantees 100% DRY parity between the CLI and the Web UI.
"""

from __future__ import annotations

import os
from pathlib import Path
import zipfile


def build_web_package(
    src_dir: Path | None = None,
    output_zip: Path | None = None,
) -> Path:
    """Packages src/gear_reduction into a zip file for Pyodide."""
    project_root = Path(__file__).resolve().parent.parent
    if src_dir is None:
        src_dir = project_root / "src" / "gear_reduction"
    if output_zip is None:
        output_zip = project_root / "web" / "python" / "gear_reduction.zip"

    output_zip.parent.mkdir(parents=True, exist_ok=True)

    if not src_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_dir}")

    # Create zip archive containing the gear_reduction package directory
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            # Exclude __pycache__ and test artifacts
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for file in files:
                if file.endswith((".pyc", ".pyo")):
                    continue
                file_path = Path(root) / file
                rel_path = file_path.relative_to(src_dir.parent)
                zf.write(file_path, arcname=str(rel_path))

    return output_zip


if __name__ == "__main__":
    out = build_web_package()
    size_kb = out.stat().st_size / 1024
    print(f"Successfully packaged web assets: {out} ({size_kb:.1f} KB)")
