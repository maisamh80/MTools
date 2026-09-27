import base64
import csv
import io
import json
import os
import shutil
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .dependencies import analyze, validate_graph
from .files import atomic_json, copy_verified, digest, inside, no_links, read_json, signature, walk

MODEL_FOLDERS = "audio_encoders background_removal checkpoints clip clip_vision configs controlnet detection diffusers diffusion_models embeddings frame_interpolation geometry_estimation gligen hypernetworks latent_upscale_models loras model_patches optical_flow photomaker sam2 style_models text_encoders unet upscale_models vae vae_approx".split()
MEDIA = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".mp4", ".webm", ".mov", ".mkv", ".avi"}
VIDEO = {".mp4", ".webm", ".mov", ".mkv", ".avi"}
TRASH = ".pwl-trash"


class Cancelled(Exception):
    pass


from .projects import Projects

class Service(Projects):
    def __init__(self, plugin, host):
        self.plugin = no_links(plugin)
        self.host = host
        for name in ("portable", "comfy", "models", "output"):
            host[name] = str(no_links(host[name]))
        output = Path(host["output"])
        if any(output.is_relative_to(r) or r.is_relative_to(output) for r in [self.plugin, Path(host["models"])]):
            raise ValueError("Gallery output root overlaps plugin code or model files")
        if output in {Path(host["comfy"]), Path(host["portable"])} or Path(host["comfy"]).is_relative_to(output):
            raise ValueError("Gallery output root cannot contain ComfyUI")
        self.data = self.plugin / "data"
        self.data.mkdir(exist_ok=True)
        self.lock_file = (self.data / "worker.lock").open("a+b")
        # Kernel lock releases on crashes; the file is metadata, not a stale PID lock.
        self.lock_file.seek(0)
        self.lock_file.write(b"0")
        self.lock_file.flush()
        self.lock_file.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.settings = read_json(self.data / "settings.json") if (self.data / "settings.json").exists() else {}
        marker = self.plugin / ".mtools-owner.json"
        if marker.exists():
            self.owner = read_json(marker)
            if self.owner.get("product") != "MTools":
                raise ValueError("Invalid installation ownership marker")
        else:
            self.owner = {"product": "MTools", "schema_version": 1, "installation_id": uuid.uuid4().hex}
            atomic_json(marker, self.owner)
        atomic_json(self.data / "installation.json", {"owner": self.owner, "plugin": str(self.plugin),
                    "output": host["output"], "host_pid": host.get("host_pid"), "comfy": host["comfy"],
                    "external_library": self.settings.get("library_root")})
        self.library_root = no_links(self.settings.get("library_root", self.data / "workflows"))
        if self.settings.get("library_root"):
            if read_json(self.library_root / ".mtools-owner.json") != self.owner:
                raise ValueError("External library ownership mismatch")
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mtools-io")
        self.jobs = {}
        self.mutex = threading.RLock()
        self.media = {}
        self.report = None
        self.stopping = False

    def close(self):
        self.stopping = True
        for job in self.jobs.values():
            job["cancel"].set()
        self.pool.shutdown(wait=True, cancel_futures=True)
        self.lock_file.close()

    def call(self, method, params):
        # Explicit allowlist; never dispatch arbitrary Python attributes.
        methods = {"projects": self.projects_list, "projects.configure": self.projects_configure, "project.get": self.project_get, "project.edit": self.project_edit, "project.file": self.project_file, "project.reveal": self.project_reveal, "destination.browse": self.destination_browse, "status": self.status, "report": self.get_report, "report.export": self.report_export,
                   "workflows": self.workflows, "workflow.get": self.workflow_get,
                   "workflow.save": self.workflow_save, "workflow.delete": self.workflow_delete,
                   "workflow.restore": self.workflow_restore, "workflow.check": self.workflow_check,
                   "gallery": self.gallery, "gallery.file": self.gallery_file,
                   "gallery.trash.list": self.trash_list, "gallery.trash": self.trash, "gallery.delete": self.gallery_delete,
                   "gallery.restore": self.restore, "gallery.purge": self.purge,
                   "gallery.open": self.open_media, "job.start": self.job_start,
                   "job.get": self.job_get, "job.cancel": self.job_cancel,
                   "uninstall.plan": self.uninstall_plan, "storage.configure": self.storage_configure}
        if self.stopping or method not in methods:
            raise ValueError("Unsupported method or worker is stopping")
        with self.mutex:
            return methods[method](**params)

    def destination_browse(self, path=None, mode='folder'):
        """Read-only folder chooser; independent of the host's desktop session."""
        if mode not in {'folder', 'zip'}:
            raise ValueError('Invalid destination format')
        if not path:
            drives = [f'{letter}:/' for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if Path(f'{letter}:/').is_dir()] if os.name == 'nt' else ['/']
            return {'path': '', 'parent': '', 'folders': [{'name': p, 'path': p} for p in drives], 'destination': None}
        folder = no_links(path)
        if not folder.is_dir():
            raise ValueError('Choose an existing folder')
        folders = []
        for entry in folder.iterdir():
            try:
                if entry.is_dir() and not entry.is_symlink() and not entry.is_junction():
                    folders.append({'name': entry.name, 'path': str(entry)})
            except OSError:
                continue
        name = 'MTools-export'
        suffix = '.zip' if mode == 'zip' else ''
        destination = folder / (name + suffix)
        index = 2
        while destination.exists():
            destination = folder / (f'{name}-{index}' + suffix)
            index += 1
        return {'path': str(folder), 'parent': str(folder.parent) if folder.parent != folder else '',
                'folders': sorted(folders, key=lambda f: f['name'].casefold()), 'destination': str(destination)}

    def status(self):
        return {"version": "0.1.0-alpha.1", "protocol_version": 1, "private_runtime": True,
                "data_path": str(self.data), "library_path": str(self.library_root), "installation_id": self.owner["installation_id"],
                "capabilities": {"external_data_location": True, "additional_gallery_roots": False,
                                 "sidebar_shortcut": True, "sidebar_placement_verified_frontends": ["1.51.10"]}, "host": self.host}

    def scan_report(self, check=lambda: None):
        check()
        models = walk(self.host["models"], cancel=check)
        check()
        portable = walk(self.host["portable"], cancel=check)
        comfy = Path(self.host["comfy"])
        root = Path(self.host["portable"])
        unique = {}
        for f in portable["files"]:
            unique[tuple(f["signature"][2:])] = f["size"]
        groups = []
        actual = {d["path"].split("/")[0] for d in models["directories"] if d["path"] != "."}
        for name in sorted(actual | set(MODEL_FOLDERS)):
            category_files = [f for f in models["files"] if f["path"].startswith(name + "/")]
            items = [dict(f, absolute_path=str(Path(self.host["models"]) / f["path"]), source_url=self.source_url(f["path"]))
                     for f in category_files if not self.is_placeholder(f)]
            groups.append({"name": name, "exists": name in actual, "files": items,
                           "size": sum(f["size"] for f in items), "count": len(items),
                           "placeholder_count": sum(self.is_placeholder(f) for f in category_files)})
        loose = [f for f in models["files"] if "/" not in f["path"]]
        if loose:
            groups.append({"name": "(models root files)", "exists": True, "files": loose,
                           "size": sum(f["size"] for f in loose), "count": len(loose)})
        external = []
        seen = set()
        for category, paths in self.host.get("model_roots", {}).items():
            for path in paths:
                p = Path(path)
                if category in {'output', 'output_loader', 'input', 'temp'} or p.is_relative_to(Path(self.host['output'])):
                    continue
                if not p.is_relative_to(Path(self.host["models"])) and path not in seen:
                    seen.add(path)
                    try:
                        external.append({"category": category, "root": path, **walk(p, cancel=check)})
                    except (ValueError, OSError) as e:
                        external.append({"category": category, "root": path, "errors": [str(e)]})
        self.report = {"scanned_at": time.time(), "groups": groups, "directories": models["directories"],
                       "portable_bytes": sum(f["size"] for f in portable["files"]),
                       "portable_unique_bytes": sum(unique.values()),
                       "comfy_bytes": sum(f["size"] for f in portable["files"] if (root / f["path"]).is_relative_to(comfy)),
                       "models_bytes": sum(f["size"] for f in models["files"]),
                       "errors": portable["errors"] + models["errors"], "external": external,
                       "measurement": "Logical bytes, not allocated disk space; links are excluded. Snapshot may change during generation."}
        return self.report

    @staticmethod
    def is_placeholder(file):
        name = Path(file['path']).name.lower()
        return file['size'] == 0 and name.startswith('put_') and name.endswith('_here')

    def source_url(self, relative):
        p = inside(self.host["models"], relative)
        sidecar = p.with_name(p.name + ".metadata.json")
        try:
            if sidecar.stat().st_size > 65536:
                return None
            data = read_json(sidecar)
            url = data.get("source_url")
            from urllib.parse import urlparse
            parsed = urlparse(url) if isinstance(url, str) else None
            return url if parsed and parsed.scheme == "https" and parsed.netloc and not parsed.username else None
        except (OSError, ValueError, AttributeError):
            return None

    def get_report(self):
        return self.report

    def report_export(self, format="json"):
        if not self.report:
            raise ValueError("Scan first")
        if format == "json":
            return {"text": json.dumps(self.report, ensure_ascii=False, indent=2)}
        if format != "csv":
            raise ValueError("Unknown export format")
        out = io.StringIO(newline="")
        writer = csv.writer(out)
        writer.writerow(["Folder", "Path", "Bytes", "Source URL"])
        for group in self.report["groups"]:
            for f in group["files"] or [{"path": "", "size": 0}]:
                row = [group["name"], f["path"], str(f["size"]), f.get("source_url") or ""]
                writer.writerow(["'" + v if v[:1] in "=+-@\t\r" and v else v for v in row])
        return {"text": out.getvalue()}

    def wfdir(self, id):
        if not isinstance(id, str) or len(id) != 32 or any(c not in "0123456789abcdef" for c in id):
            raise ValueError("Invalid workflow ID")
        return inside(self.library_root, id)

    def workflows(self, deleted=False):
        root = self.library_root
        result = []
        if root.exists():
            for p in root.iterdir():
                if p.is_dir():
                    item = self.workflow_get(p.name)
                    if bool(item.get("deleted")) == deleted:
                        result.append({k: v for k, v in item.items() if k != "graph"})
        return sorted(result, key=lambda w: w["updated_at"], reverse=True)

    def workflow_get(self, id, revision=None):
        folder = self.wfdir(id)
        current = read_json(folder / "current.json")
        rev = revision or current["revision"]
        if not isinstance(rev, int) or rev < 1:
            raise ValueError("Invalid revision")
        return read_json(folder / f"{rev}.json")

    def workflow_save(self, title, graph, description="", tags=None, cover=None, id=None, expected_revision=None):
        validate_graph(graph)
        if len(json.dumps(graph).encode()) > 20 * 1024 * 1024:
            raise ValueError("Workflow exceeds 20 MiB")
        title = title.strip()
        if not title or len(title) > 200 or len(description) > 20000:
            raise ValueError("Title is required (max 200); description max 20000 characters")
        if not isinstance(tags or [], list) or any(not isinstance(t, str) or len(t) > 80 for t in tags or []) or len(tags or []) > 40:
            raise ValueError("Invalid tags")
        if cover:
            self.validate_cover(cover)
        id = id or uuid.uuid4().hex
        folder = self.wfdir(id)
        revision = 1
        if folder.exists():
            old = self.workflow_get(id)
            if old["revision"] != expected_revision:
                raise ValueError("Revision conflict: reload before saving")
            revision = old["revision"] + 1
        item = {"schema_version": 1, "id": id, "revision": revision, "title": title,
                "description": description, "tags": tags or [], "cover": cover, "graph": graph,
                "updated_at": time.time(), "deleted": False}
        # Immutable revision must exist before switching current pointer.
        revpath = folder / f"{revision}.json"
        if revpath.exists():
            raise ValueError("Uncommitted revision exists; manual recovery required")
        atomic_json(revpath, item)
        atomic_json(folder / "current.json", {"revision": revision})
        return item

    @staticmethod
    def validate_cover(cover):
        # Browser decodes and converts cover images to bounded PNG before upload.
        if not isinstance(cover, str) or not cover.startswith("data:image/png;base64,"):
            raise ValueError("Cover must be a PNG data URL")
        raw = base64.b64decode(cover.split(",", 1)[1], validate=True)
        if len(raw) > 10 * 1024 * 1024 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR" or len(raw) < 33:
            raise ValueError("Invalid PNG cover or cover exceeds 10 MiB")
        w, h = int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")
        if not 0 < w <= 4096 or not 0 < h <= 4096:
            raise ValueError("Cover dimensions must be 1–4096 pixels")

    def workflow_delete(self, id, expected_revision, deleted=True):
        item = self.workflow_get(id)
        if item["revision"] != expected_revision:
            raise ValueError("Revision conflict")
        item.update(deleted=deleted, revision=item["revision"] + 1, updated_at=time.time())
        folder = self.wfdir(id)
        if (folder / f'{item["revision"]}.json').exists():
            raise ValueError("Uncommitted revision exists")
        atomic_json(folder / f'{item["revision"]}.json', item)
        atomic_json(folder / "current.json", {"revision": item["revision"]})
        return item

    def workflow_restore(self, id, expected_revision, revision=None):
        if revision is None:
            return self.workflow_delete(id, expected_revision, False)
        item = self.workflow_get(id, revision)
        return self.workflow_save(item["title"], item["graph"], item["description"], item["tags"],
                                  item["cover"], id, expected_revision)

    def workflow_check(self, id):
        return {**analyze(self.workflow_get(id)["graph"], self.host), "checked_at": time.time()}

    def gallery(self):
        snapshot = walk(self.host["output"], exclude=(TRASH,), skip_partials=True)
        media = {}
        for f in snapshot["files"]:
            # Stable ID per path, but version must match for destructive operations.
            import hashlib
            id = hashlib.sha256(f["path"].encode()).hexdigest()[:32]
            suffix = Path(f["path"]).suffix.lower()
            media[id] = dict(f, id=id, kind="video" if suffix in VIDEO else "image" if suffix in MEDIA else "file")
        self.media = media
        return {"files": list(media.values()), "errors": snapshot["errors"], "root": self.host["output"]}

    def gallery_file(self, id, version=None):
        if id not in self.media:
            raise ValueError("Unknown file; refresh gallery")
        item = self.media[id]
        path = inside(self.host["output"], item["path"])
        if signature(path) != item["signature"] or (version and version != item["signature"]):
            raise ValueError("File changed; refresh gallery")
        return {**item, "absolute_path": str(path)}

    def ensure_idle(self):
        if any(j["status"] in {"queued", "running"} for j in self.jobs.values()):
            raise ValueError("Wait for or cancel the active disk job")

    def gallery_delete(self, id, version, confirmation):
        self.ensure_idle()
        if confirmation != 'PERMANENTLY DELETE':
            raise ValueError('Confirm permanent deletion first')
        item = self.gallery_file(id, version)
        path = Path(item['absolute_path'])
        before = signature(path)
        time.sleep(.15)
        if signature(path) != before:
            raise ValueError('File is still being written; try again after generation finishes')
        path.unlink()
        self.media.pop(id, None)
        return {'deleted': id, 'path': item['path'], 'absolute_path': str(path)}

    def trash_root(self, create=False):
        root = inside(self.host["output"], TRASH)
        marker = root / ".mtools-owner.json"
        if root.exists():
            if not marker.exists() or read_json(marker) != self.owner:
                raise ValueError("Trash belongs to another installation or has no ownership marker")
        elif create:
            root.mkdir()
            atomic_json(marker, self.owner)
        return root

    def trash_list(self):
        root = self.trash_root()
        if not root.exists():
            return []
        items = []
        for p in root.glob("*.json"):
            if p.name.startswith("."):
                continue
            item = read_json(p)
            item["payload_exists"] = (root / item["id"]).is_file()
            items.append(item)
        return items

    def trash(self, files):
        self.ensure_idle()
        results = []
        root = self.trash_root(create=True)
        for selection in files:
            try:
                item = self.gallery_file(selection["id"], selection["version"])
                path = Path(item.pop("absolute_path"))
                before = signature(path)
                time.sleep(0.15)
                if signature(path) != before:
                    raise ValueError("File is still changing")
                id = uuid.uuid4().hex
                record = {"id": id, "original": item["path"], "signature": before, "deleted_at": time.time(), "state": "pending"}
                atomic_json(root / f"{id}.json", record)
                # On Windows, rename fails if producer holds the file without delete sharing.
                path.rename(root / id)
                record["state"] = "trashed"
                atomic_json(root / f"{id}.json", record)
                results.append({"id": selection["id"], "ok": True})
            except (OSError, ValueError, KeyError) as e:
                results.append({"id": selection.get("id"), "ok": False, "error": str(e)})
        return results

    def trash_item(self, id):
        if not isinstance(id, str) or len(id) != 32 or any(c not in "0123456789abcdef" for c in id):
            raise ValueError("Invalid trash ID")
        root = self.trash_root()
        return root, read_json(root / f"{id}.json")

    def restore(self, id):
        self.ensure_idle()
        root, item = self.trash_item(id)
        target = inside(self.host["output"], item["original"])
        if target.exists():
            raise ValueError("Original path exists. Rename that file before restoring; nothing overwritten.")
        if [str(v) for v in signature(root / id)] != [str(v) for v in item["signature"]]:
            raise ValueError("Trash payload changed")
        target.parent.mkdir(parents=True, exist_ok=True)
        (root / id).rename(target)
        (root / f"{id}.json").unlink()
        return {"restored": item["original"]}

    def purge(self, id, confirmation):
        self.ensure_idle()
        if confirmation != "PERMANENTLY DELETE":
            raise ValueError("Explicit permanent deletion confirmation required")
        root, item = self.trash_item(id)
        payload = inside(root, id)
        if payload.exists():
            if [str(v) for v in signature(payload)] != [str(v) for v in item["signature"]]:
                raise ValueError("Trash payload changed")
            payload.unlink()
        (root / f"{id}.json").unlink()
        return {"purged": id}

    def open_media(self, id, reveal=False):
        item = self.gallery_file(id)
        if os.name != "nt":
            raise ValueError("This action requires Windows")
        path = Path(item["absolute_path"])
        if reveal:
            from .windows import reveal_file
            reveal_file(path)
        elif path.suffix.lower() in MEDIA:
            os.startfile(str(path))
        else:
            raise ValueError("Only image/video files may be opened")
        return {"opened": True}

    def job_start(self, kind, options=None, key=None):
        if kind not in {"scan", "export", "backup", "library.backup", "project.save", "project.import", "project.export", "project.update"}:
            raise ValueError("Unknown job kind")
        if key:
            for id, job in self.jobs.items():
                if job.get("key") == key:
                    return {"id": id}
        id = uuid.uuid4().hex
        job = {"id": id, "key": key, "kind": kind, "status": "queued", "progress": 0,
               "cancel": threading.Event(), "created_at": time.time()}
        self.jobs[id] = job
        def run():
            job["status"] = "running"
            def check():
                if job["cancel"].is_set():
                    raise Cancelled("Cancelled; any partial destination is retained and labeled incomplete")
            try:
                check()
                job["result"] = self.scan_report(check) if kind == "scan" else self.project_job(kind, options or {}, job, check) if kind.startswith("project.") else self.package(kind, options or {}, job, check)
                job["status"] = "complete"
                job["progress"] = 1
            except Cancelled as e:
                job.update(status="cancelled", error=str(e))
            except Exception as e:
                job.update(status="failed", error=str(e))
        self.pool.submit(run)
        return {"id": id}

    def job_get(self, id):
        return {k: v for k, v in self.jobs[id].items() if k != "cancel"}

    def job_cancel(self, id):
        self.jobs[id]["cancel"].set()
        return {"requested": True}

    def destination(self, path):
        p = no_links(path)
        if not Path(path).is_absolute():
            raise ValueError("Choose an absolute destination path")
        protected = [self.plugin, Path(self.host["portable"]), Path(self.host["output"])]
        protected += [Path(p) for roots in self.host.get("model_roots", {}).values() for p in roots]
        if any(p.is_relative_to(r) or r.is_relative_to(p) for r in protected):
            raise ValueError("Destination overlaps a protected installation, model or output root")
        if p.exists():
            raise ValueError("Destination must be a new folder/file; overwriting is not allowed")
        if not p.parent.is_dir():
            raise ValueError("Destination parent must already exist")
        return p

    def package(self, kind, options, job, check):
        dest = self.destination(options["destination"])
        zipped = options.get("zip", False)
        partial = dest.with_name(dest.name + ".partial")
        if partial.exists():
            raise ValueError("Partial destination exists; choose another destination")
        files, directories, extras = [], set(), {}
        manifest = {"schema_version": 1, "kind": kind, "created_at": time.time(), "complete": False,
                    "files": [], "errors": [], "exclusions": [], "directories": [], "snapshot_notice": "Files created after the snapshot are not included."}
        if kind == "export":
            with self.mutex:
                item = self.workflow_get(options["id"])
            report = analyze(item["graph"], self.host)
            if report["status"] != "complete" and not options.get("allow_incomplete"):
                raise ValueError("Unresolved requirements. Explicitly allow an incomplete package or resolve them first.")
            snapshot = walk(self.host["models"], cancel=check)
            if snapshot["errors"]:
                raise ValueError("Model directory structure could not be fully scanned")
            for d in snapshot["directories"]:
                directories.add("models" if d["path"] == "." else "models/" + d["path"])
                manifest["directories"].append(dict(d, relative_path="models/" + d["path"]))
            # Screenshot baseline is preserved even when source installation lacks a category.
            directories.update("models/" + n for n in MODEL_FOLDERS)
            seen = set()
            for ref in report["models"]:
                if ref["status"] == "found" and ref["target"] not in seen:
                    seen.add(ref["target"])
                    files.append((Path(ref["source"]), "models/" + ref["target"], signature(ref["source"])))
            # Strip machine paths from portable diagnostics.
            clean = json.loads(json.dumps(report))
            for ref in clean["models"]:
                ref.pop("source", None)
                ref.pop("matches", None)
            manifest["requirements"] = clean
            manifest["requirements_complete"] = report["status"] == "complete"
            extras["workflow.json"] = item["graph"]
            extras["metadata.json"] = {k: v for k, v in item.items() if k != "graph"}
            extras["custom-nodes.json"] = report["custom_nodes"]
        elif kind == "backup":
            snapshot = walk(self.host["output"], exclude=(TRASH,), skip_partials=True, cancel=check)
            if snapshot["errors"]:
                raise ValueError("Output snapshot incomplete: " + str(snapshot["errors"]))
            selection = options.get("files")
            selected = None
            if selection is not None:
                selected = {self.gallery_file(s["id"], s["version"])["path"] for s in selection}
            for f in snapshot["files"]:
                if selected is None or f["path"] in selected:
                    files.append((Path(self.host["output"]) / f["path"], "outputs/main/" + f["path"], f["signature"]))
            if selected is None:
                directories.update("outputs/main/" + d["path"] for d in snapshot["directories"])
            manifest["exclusions"] = snapshot["skipped"]
        else:
            with self.mutex:
                library = self.workflows() + self.workflows(deleted=True)
            extras["library.json"] = [self.workflow_get(w["id"]) for w in library]
        total = sum(s[0] for _, _, s in files)
        if shutil.disk_usage(dest.parent).free < total * (2 if zipped else 1) + 16 * 1024 * 1024:
            raise ValueError("Insufficient free space (including verification staging)")
        partial.mkdir()
        try:
            for d in sorted(directories):
                inside(partial, d).mkdir(parents=True, exist_ok=True)
            for name, data in extras.items():
                atomic_json(inside(partial, name), data)
            for i, (source, target, version) in enumerate(files):
                check()
                sha = copy_verified(source, inside(partial, target), version, check)
                manifest["files"].append({"path": target, "size": version[0], "mtime_ns": version[1], "sha256": sha})
                job["progress"] = (i + 1) / max(1, len(files)) * 0.9
            for d in manifest["directories"]:
                prefix = d["relative_path"].rstrip("/.") + "/"
                d["exported_file_count"] = sum(f["path"].startswith(prefix) for f in manifest["files"])
            manifest["complete"] = True
            atomic_json(partial / "manifest.json", manifest)
            (partial / "README.txt").write_text("M Tools verified copy\nCopy models/ subfolders into the target ComfyUI/models/ using the same paths.\nReview custom-nodes.json and install the listed repositories and their Python requirements separately.\nNode source alone does not guarantee compatibility. No automatic installs.\nFor gallery backups copy outputs/main/ to your chosen output folder without overwriting existing files.\nSee manifest.json for unresolved requirements, file hashes and snapshot limitations.\n", encoding="utf-8")
            check()
            if zipped:
                zip_temp = dest.with_name(dest.name + ".zip.partial")
                with zipfile.ZipFile(zip_temp, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
                    for p in sorted(partial.rglob("*")):
                        check()
                        z.write(p, p.relative_to(partial).as_posix())
                with zipfile.ZipFile(zip_temp) as z:
                    for entry in z.infolist():
                        check()
                        if entry.is_dir():
                            continue
                        import hashlib
                        h = hashlib.sha256()
                        with z.open(entry) as f:
                            for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
                                check()
                                h.update(block)
                        if h.hexdigest() != digest(inside(partial, entry.filename), check):
                            raise ValueError("ZIP verification failed")
                # No replacement of a user-created destination between checks.
                if dest.exists():
                    raise ValueError("Destination appeared during export")
                zip_temp.rename(dest)
                no_links(partial)
                shutil.rmtree(partial)
            else:
                if dest.exists():
                    raise ValueError("Destination appeared during export")
                partial.rename(dest)
            return {"destination": str(dest), "file_count": len(files), "bytes": total,
                    "requirements_complete": manifest.get("requirements_complete", True)}
        except Exception as e:
            manifest.update(complete=False, errors=[str(e)])
            if partial.exists():
                atomic_json(partial / "manifest.json", manifest)
            raise

    def uninstall_plan(self):
        self.ensure_idle()
        trash = self.trash_list()
        return {"installation_id": self.owner["installation_id"], "plugin": str(self.plugin), "external_library": self.settings.get("library_root"),
                "trash_count": len(trash), "blocked": bool(trash),
                "instructions": "Restore or explicitly purge every trash item. Close ComfyUI yourself, then run scripts/Uninstall.ps1. The helper verifies ownership and removes this entire plugin folder. Reload all browser tabs afterwards.",
                "preserved": ["ComfyUI", "models", "original outputs", "user export packages and backups", "independent Projects archives"]}

    def storage_configure(self, destination):
        self.ensure_idle()
        if self.workflows() or self.workflows(deleted=True) or self.settings.get("library_root"):
            raise ValueError("Choose the library location before saving your first workflow. Existing libraries are not silently moved.")
        dest = self.destination(destination)
        dest.mkdir()
        atomic_json(dest / ".mtools-owner.json", self.owner)
        self.settings["library_root"] = str(dest)
        # Record ownership before enabling the new location, so offline cleanup sees it.
        install = read_json(self.data / "installation.json")
        install["external_library"] = str(dest)
        atomic_json(self.data / "installation.json", install)
        atomic_json(self.data / "settings.json", self.settings)
        self.library_root = dest
        return {"library_path": str(dest)}
