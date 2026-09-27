"""Conservative filesystem primitives. Never follow junctions or symbolic links."""
import hashlib
import json
import os
import stat
import uuid
from pathlib import Path


def no_links(path):
    path = Path(os.path.abspath(path))
    for part in [*reversed(path.parents), path]:
        try:
            s = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(s.st_mode) or getattr(s, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"Links/reparse points are not supported: {part}")
    return path


def inside(root, relative):
    root = no_links(root)
    relative = str(relative).replace("\\", "/")
    rel = Path(relative)
    if rel.is_absolute() or rel.drive or any(part == ".." or ":" in part or "\x00" in part for part in rel.parts):
        raise ValueError("Expected a relative path without traversal or alternate data streams")
    p = no_links(root / rel)
    if not p.is_relative_to(root) or p == root:
        raise ValueError("Path must be a child of the approved root")
    return p


def atomic_json(path, data):
    path = no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("x", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_json(path):
    with no_links(path).open(encoding="utf-8") as f:
        return json.load(f)


def signature(path):
    s = no_links(path).stat()
    # Nanoseconds and Windows file IDs exceed JavaScript's safe integer range.
    return [s.st_size, str(s.st_mtime_ns), str(s.st_dev), str(s.st_ino)]


def digest(path, cancel=lambda: None):
    h = hashlib.sha256()
    with no_links(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            cancel()
            h.update(block)
    return h.hexdigest()


def copy_verified(src, dst, expected, cancel=lambda: None):
    if signature(src) != expected:
        raise ValueError("Source changed since snapshot")
    dst = no_links(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    with no_links(src).open("rb") as source, dst.open("xb") as target:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            cancel()
            h.update(block)
            target.write(block)
        target.flush()
        os.fsync(target.fileno())
    if signature(src) != expected or digest(dst, cancel) != h.hexdigest():
        raise ValueError("Source changed or destination verification failed")
    return h.hexdigest()


def walk(root, exclude=(), skip_partials=False, cancel=lambda: None):
    """Return a complete snapshot, including empty directories and access errors."""
    root = no_links(root)
    result = {"directories": [], "files": [], "errors": [], "skipped": []}
    if not root.is_dir():
        result["errors"].append({"path": ".", "error": "Directory missing"})
        return result
    def visit(folder):
        cancel()
        try:
            entries = sorted(os.scandir(folder), key=lambda e: e.name.casefold())
        except OSError as e:
            result["errors"].append({"path": str(folder.relative_to(root)), "error": str(e)})
            return
        result["directories"].append({"path": folder.relative_to(root).as_posix(), "source_empty": not entries})
        for entry in entries:
            cancel()
            p = Path(entry.path)
            rel = p.relative_to(root).as_posix()
            if entry.name in exclude or (skip_partials and entry.name.endswith((".partial", ".tmp"))):
                result["skipped"].append(rel)
                continue
            try:
                no_links(p)
                if entry.is_dir(follow_symlinks=False):
                    visit(p)
                elif entry.is_file(follow_symlinks=False):
                    s = signature(p)
                    result["files"].append({"path": rel, "size": s[0], "mtime_ns": s[1], "signature": s})
            except (OSError, ValueError) as e:
                result["errors"].append({"path": rel, "error": str(e)})
    visit(root)
    return result
