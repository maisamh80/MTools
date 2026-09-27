"""Build a source ZIP without private paths, user data or development caches."""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("destination", type=Path)
args = parser.parse_args()
excluded = {".git", "data", "runtime", "__pycache__", "node_modules", ".mtools-owner.json", "playwright-report", "test-results"}
with ZipFile(args.destination, "x", ZIP_DEFLATED) as z:
    for p in sorted(root.rglob("*")):
        relative = p.relative_to(root)
        if p.is_file() and not set(relative.parts) & excluded and p.suffix != ".pyc":
            z.write(p, Path("MTools") / relative)
sha = hashlib.sha256(args.destination.read_bytes()).hexdigest()
args.destination.with_suffix(args.destination.suffix + ".sha256").write_text(f"{sha}  {args.destination.name}\n")
print(args.destination)
