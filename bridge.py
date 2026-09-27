"""Host-side bridge: snapshot, private-process transport, vetted media streaming."""
import asyncio
import configparser
import ipaddress
import json
import os
import secrets
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from .asset_sync import hide_deleted_asset

ROOT = Path(__file__).resolve().parent


def repository_info(module_file):
    from .mtools.files import no_links
    result = {}
    p = Path(module_file).parent
    for parent in [p, *p.parents]:
        git = parent / ".git"
        if git.is_dir():
            try:
                config = configparser.ConfigParser(interpolation=None)
                config.read(no_links(git / "config"), encoding="utf-8")
                raw = config.get('remote "origin"', "url", fallback="")
                if raw.startswith("git@github.com:"):
                    raw = "https://github.com/" + raw.split(":", 1)[1]
                u = urlsplit(raw)
                if u.scheme == "https" and u.hostname:
                    result["repository"] = urlunsplit(("https", u.hostname, u.path, "", ""))
                head = no_links(git / "HEAD").read_text().strip()
                if head.startswith("ref: "):
                    ref = no_links(git / head[5:])
                    if ref.is_relative_to(git) and ref.is_file():
                        head = ref.read_text().strip()
                if len(head) == 40 and all(c in "0123456789abcdef" for c in head):
                    result["commit"] = head
                result["local_changes"] = "not_checked"
            except (OSError, ValueError, configparser.Error):
                pass
            break
        if parent.name == "custom_nodes":
            break
    return result


def host_snapshot():
    import folder_paths
    import nodes
    comfy = Path(folder_paths.base_path).resolve()
    portable = comfy.parent
    if os.name != "nt" or not (portable / "python_embeded").is_dir():
        raise ValueError("M Tools currently requires Windows ComfyUI Portable (python_embeded folder)")
    registry = {}
    for name, cls in nodes.NODE_CLASS_MAPPINGS.items():
        module = sys.modules.get(cls.__module__)
        file = getattr(module, "__file__", "") or ""
        custom = "custom_nodes" in Path(file).parts
        registry[name] = {"custom": custom, **(repository_info(file) if custom else {})}
    return {"portable": str(portable), "comfy": str(comfy), "models": str(Path(folder_paths.models_dir).absolute()),
            "output": str(Path(folder_paths.get_output_directory()).absolute()),
            "input": str(Path(folder_paths.get_input_directory()).absolute()),
            "model_roots": {key: [str(Path(p).absolute()) for p in value[0]]
                            for key, value in folder_paths.folder_names_and_paths.items()},
            "nodes": registry, "host_pid": os.getpid()}


class PrivateWorker:
    def __init__(self):
        self.process = None
        self.lock = asyncio.Lock()
        self.counter = 0
        self.stderr_task = None

    async def drain_errors(self):
        import logging
        while self.process:
            line = await self.process.stderr.readline()
            if not line:
                break
            logging.getLogger("MTools").warning("Worker: %s", line.decode("utf-8", errors="replace").rstrip())

    async def exchange(self, method, params, timeout=30):
        self.counter += 1
        req = {"protocol_version": 1, "request_id": self.counter, "method": method, "params": params}
        self.process.stdin.write((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
        await self.process.stdin.drain()
        try:
            line = await asyncio.wait_for(self.process.stdout.readline(), timeout)
        except asyncio.TimeoutError:
            await self.close()
            raise ValueError("Private worker timed out; stopped to prevent response mismatch")
        if not line:
            raise ValueError("Private worker exited")
        reply = json.loads(line)
        if reply.get("request_id") != self.counter:
            raise ValueError("Worker protocol response mismatch")
        if "error" in reply:
            raise ValueError(reply["error"]["message"])
        return reply["result"]

    async def call(self, method, params):
        async with self.lock:
            if not self.process or self.process.returncode is not None:
                from .mtools.files import no_links
                exe = no_links(ROOT / "runtime" / "python" / "python.exe")
                if not exe.is_file():
                    raise ValueError("Private runtime is not bundled. Prepare a release with scripts/Prepare-Runtime.ps1; M Tools will never use ComfyUI's Python as a fallback.")
                env = {k: v for k, v in os.environ.items() if k.upper() not in {"PYTHONPATH", "PYTHONHOME"}}
                env["PYTHONIOENCODING"] = "utf-8"
                self.process = await asyncio.create_subprocess_exec(
                    str(exe), "-I", "-B", "-m", "mtools.worker", cwd=str(ROOT), env=env,
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                    limit=64 * 1024 * 1024, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                self.stderr_task = asyncio.create_task(self.drain_errors())
                await self.exchange("initialize", {"host": host_snapshot()}, 10)
            return await self.exchange(method, params)

    async def close(self):
        if self.process and self.process.returncode is None:
            self.process.stdin.close()
            try:
                await asyncio.wait_for(self.process.wait(), 10)
            except asyncio.TimeoutError:
                # This is our private worker, never ComfyUI or another process.
                self.process.terminate()
                await self.process.wait()
        self.process = None


def register():
    from aiohttp import web
    from server import PromptServer
    from .mtools.files import no_links
    routes = PromptServer.instance.routes
    worker = PrivateWorker()
    nonce = secrets.token_urlsafe(32)

    def guard(request, mutation=False):
        try:
            if not ipaddress.ip_address(request.remote).is_loopback:
                raise ValueError()
        except (ValueError, TypeError):
            raise web.HTTPForbidden(text="M Tools is local-only")
        hostname = request.host.split(":")[0].strip("[]").lower()
        if hostname not in {"localhost", "127.0.0.1"} and not request.host.startswith("[::1]"):
            raise web.HTTPForbidden(text="Untrusted host")
        origin = request.headers.get("Origin")
        if origin and origin != f"{request.scheme}://{request.host}":
            raise web.HTTPForbidden(text="Cross-origin requests are forbidden")
        if request.headers.get("Sec-Fetch-Site") not in {None, "same-origin", "none"}:
            raise web.HTTPForbidden(text="Cross-origin requests are forbidden")
        if mutation and not secrets.compare_digest(request.headers.get("X-MTools-Nonce", ""), nonce):
            raise web.HTTPForbidden(text="Invalid request nonce")

    @routes.get("/mtools/v1/session")
    async def session(request):
        guard(request)
        if request.headers.get("X-MTools-Client") != "1":
            raise web.HTTPForbidden()
        response = web.json_response({"nonce": nonce, "version": "1.0.0"})
        response.set_cookie("mtools-session", nonce, httponly=True, samesite="Strict", path="/mtools/")
        response.headers["Cache-Control"] = "no-store"
        return response

    @routes.post("/mtools/v1/rpc")
    async def rpc(request):
        guard(request, True)
        # Read with an explicit cap instead of altering ComfyUI's application limit.
        body = bytearray()
        async for chunk in request.content.iter_chunked(65536):
            body.extend(chunk)
            if len(body) > 44 * 1024 * 1024:
                raise web.HTTPRequestEntityTooLarge(max_size=44 * 1024 * 1024, actual_size=len(body))
        try:
            data = json.loads(body)
            if data.get("method") == "session.clear":
                response = web.json_response({"result": {"cleared": True}})
                response.del_cookie("mtools-session", path="/mtools/")
                return response
            if data.get('method') == 'project.capture':
                from .project_capture import capture_project
                p = data.get('params', {})
                result = capture_project(p['graph'], p['prompt'], host_snapshot(), PromptServer.instance.prompt_queue.get_history())
                return web.json_response({'result': result})
            result = await worker.call(data["method"], data.get("params", {}))
            if data['method'] == 'gallery.delete':
                try:
                    result['assets_synced'] = await asyncio.to_thread(hide_deleted_asset, result.pop('absolute_path'))
                except Exception as e:
                    result.pop('absolute_path', None)
                    result['warning'] = 'File deleted. Native Assets refresh needs attention: ' + str(e)
            return web.json_response({"result": result}, headers={"Cache-Control": "no-store"})
        except (ValueError, KeyError, TypeError, OSError) as e:
            return web.json_response({"error": str(e)}, status=400)

    @routes.post('/mtools/v1/project-upload')
    async def project_upload(request):
        guard(request, True)
        token = uuid.uuid4().hex
        directory = no_links(ROOT / 'data' / 'project-uploads')
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / token
        size = 0
        try:
            with path.open('xb') as target:
                async for chunk in request.content.iter_chunked(1024*1024):
                    size += len(chunk)
                    if size > 50*1024**3:
                        raise ValueError('File exceeds 50 GiB upload limit')
                    await asyncio.to_thread(target.write, chunk)
            return web.json_response({'token': token})
        except Exception:
            path.unlink(missing_ok=True)
            raise

    @routes.get('/mtools/v1/project-media/{id}')
    async def project_media(request):
        guard(request)
        if not secrets.compare_digest(request.cookies.get('mtools-session', ''), nonce):
            raise web.HTTPForbidden()
        try:
            item = await worker.call('project.file', {'id': request.match_info['id'], 'path': request.query.get('path', '')})
            path = no_links(item['path'])
            response = web.FileResponse(path, headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
            if path.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.gif','.mp4','.webm','.wav','.mp3','.ogg'} or request.query.get('download'):
                from urllib.parse import quote
                response.headers['Content-Disposition'] = "attachment; filename*=UTF-8''" + quote(path.name)
            return response
        except (ValueError, OSError) as e:
            raise web.HTTPNotFound(text=str(e))

    @routes.get("/mtools/v1/media/{id}")
    async def media(request):
        guard(request)
        if not secrets.compare_digest(request.cookies.get("mtools-session", ""), nonce):
            raise web.HTTPForbidden()
        try:
            item = await worker.call("gallery.file", {"id": request.match_info["id"]})
            if item["kind"] not in {"image", "video"}:
                raise web.HTTPForbidden(text="Preview unavailable for this file type")
            # FileResponse supports byte ranges and streams without buffering a large video.
            path = no_links(item["absolute_path"])
            return web.FileResponse(path, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        except ValueError as e:
            raise web.HTTPNotFound(text=str(e))

    async def shutdown(app):
        await worker.close()
    PromptServer.instance.app.on_shutdown.append(shutdown)
