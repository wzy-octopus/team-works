"""Build a Linux-safe deploy ZIP with forward-slash entry names.

PowerShell's Compress-Archive writes ZIP entries with backslash separators,
which Linux/Azure-Oryx treats as literal filenames (not directories) -> the
`app/` package never exists -> `ModuleNotFoundError: No module named 'app'`.

Usage:
    python makezip.py <stage_dir> <output_zip>
"""

import os
import sys
import zipfile


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    stage, out = sys.argv[1], sys.argv[2]
    if os.path.exists(out):
        os.remove(out)

    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(stage):
            for f in files:
                full = os.path.join(root, f)
                arc = os.path.relpath(full, stage).replace(os.sep, "/")
                z.write(full, arc)
                n += 1

    with zipfile.ZipFile(out) as z:
        bad = [x for x in z.namelist() if "\\" in x]
    print(f"files zipped: {n}, backslash entries (must be 0): {len(bad)}")
    if bad:
        raise SystemExit("ERROR: backslash entries present -- deploy would fail on Linux")
    print(f"zip size MB: {round(os.path.getsize(out) / 1024 / 1024, 2)}")


if __name__ == "__main__":
    main()
