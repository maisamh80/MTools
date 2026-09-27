import json
import os
import subprocess
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from mtools.dependencies import ADAPTERS, analyze
from mtools.files import copy_verified, digest, inside, signature, walk
from mtools.service import MODEL_FOLDERS, Service, Cancelled


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mtools-test-")
        self.root = Path(self.temp.name)
        self.portable = self.root / "Portable"
        self.comfy = self.portable / "ComfyUI"
        self.plugin = self.comfy / "custom_nodes" / "MTools"
        self.models = self.comfy / "models"
        self.output = self.comfy / "output"
        for path in [self.plugin, self.output, self.portable / "python_embeded"]:
            path.mkdir(parents=True)
        for folder in MODEL_FOLDERS:
            (self.models / folder).mkdir(parents=True)
        self.host = {"portable": str(self.portable), "comfy": str(self.comfy), "models": str(self.models), "output": str(self.output),
                     "nodes": {name: {"custom": False} for name in ADAPTERS}, "model_roots": {f: [str(self.models / f)] for f in MODEL_FOLDERS}}
        self.host["model_roots"]["diffusion_models"] += [str(self.models / "unet")]
        self.host["model_roots"]["text_encoders"] += [str(self.models / "clip")]
        self.s = Service(self.plugin, self.host)

    def tearDown(self):
        self.s.close()
        self.temp.cleanup()

    def graph(self, name="model.safetensors", kind="UNETLoader"):
        return {"version": .4, "nodes": [{"id": 1, "type": kind, "widgets_values": [name]}], "links": []}

    def save(self, graph=None):
        return self.s.workflow_save("آزمایش", graph or self.graph())

    def job(self, kind, options):
        id = self.s.call("job.start", {"kind": kind, "options": options})["id"]
        deadline = time.time() + 10
        while time.time() < deadline:
            result = self.s.call("job.get", {"id": id})
            if result["status"] in {"complete", "failed", "cancelled"}:
                return result
            time.sleep(.01)
        self.fail("Job timeout")

    def test_inventory_preserves_27_and_unknown_empty_folders(self):
        (self.models / "future_encoder" / "empty").mkdir(parents=True)
        (self.models / "unet" / "مدل.safetensors").write_bytes(b"1234567")
        (self.models / "configs" / "test.tmp").write_bytes(b"temp")
        report = self.s.scan_report()
        self.assertEqual(len(report["groups"]), 28)
        self.assertEqual(report["models_bytes"], 11)
        self.assertTrue(any(d["path"] == "future_encoder/empty" and d["source_empty"] for d in report["directories"]))

    def test_marker_only_category_and_output_loader(self):
        (self.models / 'audio_encoders' / 'put_audio_encoders_here').touch()
        (self.models / 'clip' / 'put_clip_here').write_text('real nonempty file')
        self.host['model_roots']['output_loader'] = [str(self.output)]
        report = self.s.scan_report()
        groups = {g['name']: g for g in report['groups']}
        self.assertEqual(groups['audio_encoders']['count'], 0)
        self.assertEqual(groups['audio_encoders']['placeholder_count'], 1)
        self.assertEqual(groups['clip']['count'], 1)
        self.assertEqual(report['external'], [])

    def test_destination_browser_is_readonly_and_avoids_collisions(self):
        (self.root / 'MTools-export').mkdir()
        before = set(self.root.iterdir())
        data = self.s.call('destination.browse', {'path': str(self.root)})
        self.assertEqual(Path(data['destination']), self.root / 'MTools-export-2')
        self.assertTrue(any(f['name'] == 'Portable' for f in data['folders']))
        archive = self.s.call('destination.browse', {'path': str(self.root), 'mode': 'zip'})
        self.assertEqual(Path(archive['destination']), self.root / 'MTools-export.zip')
        self.assertEqual(set(self.root.iterdir()), before)
        with self.assertRaises(ValueError):
            self.s.call('destination.browse', {'path': str(self.root / 'missing')})

    def test_gallery_delete_browser_roundtrip_and_confirmation(self):
        path = self.output / 'delete-test.txt'
        path.write_text('fixture')
        item = self.s.gallery()['files'][0]
        for value in item['signature'][1:]:
            self.assertIsInstance(value, str)
        browser = json.loads(subprocess.check_output(['node', '-e',
            'process.stdout.write(JSON.stringify(JSON.parse(process.argv[1])))', json.dumps(item)], text=True))
        with self.assertRaises(ValueError):
            self.s.gallery_delete(item['id'], browser['signature'], 'no')
        self.assertTrue(path.exists())
        self.s.gallery_delete(item['id'], browser['signature'], 'PERMANENTLY DELETE')
        self.assertFalse(path.exists())
        self.assertEqual(self.s.gallery()['files'], [])

    def test_aura_flow_patch_has_no_file_dependencies(self):
        self.host['nodes']['ModelSamplingAuraFlow'] = {'custom': False}
        report = analyze({'nodes': [{'id': 69, 'type': 'ModelSamplingAuraFlow', 'widgets_values': [3.0]}]}, self.host)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['unresolved'], [])

    def test_alias_resolution_preserves_physical_unet(self):
        (self.models / "unet" / "model.safetensors").write_bytes(b"model")
        report = analyze(self.graph(), self.host)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["models"][0]["target"], "unet/model.safetensors")

    def test_alias_resolution_clip(self):
        (self.models / "clip" / "clip.safetensors").write_bytes(b"clip")
        r = analyze(self.graph("clip.safetensors", "CLIPLoader"), self.host)
        self.assertEqual(r["models"][0]["target"], "clip/clip.safetensors")

    def test_ambiguity_is_not_complete(self):
        for folder in ["unet", "diffusion_models"]:
            (self.models / folder / "model.safetensors").write_bytes(b"m")
        r = analyze(self.graph(), self.host)
        self.assertEqual(r["models"][0]["status"], "ambiguous")
        self.assertEqual(r["status"], "needs_attention")

    def test_linked_and_unknown_are_not_complete(self):
        graph = self.graph()
        graph["nodes"][0]["inputs"] = [{"name": "unet_name", "link": 42}]
        self.assertEqual(analyze(graph, self.host)["models"][0]["status"], "unsupported")
        self.assertEqual(analyze(self.graph(kind="UnknownLoader"), self.host)["status"], "needs_attention")

    def test_nested_subgraphs_are_checked(self):
        graph = {"nodes": [{"id": 1, "type": "subgraph-id"}], "definitions": {"subgraphs": [{"id": "subgraph-id", "nodes": self.graph()["nodes"]}]}}
        self.assertEqual(analyze(graph, self.host)["models"][0]["status"], "missing")

    def test_external_model_needs_mapping(self):
        ext = self.root / "External"
        ext.mkdir()
        (ext / "model.safetensors").write_bytes(b"x")
        self.host["model_roots"]["diffusion_models"].append(str(ext))
        self.assertEqual(analyze(self.graph(), self.host)["models"][0]["status"], "external")

    def test_revision_conflict_and_recovery(self):
        item = self.save()
        with self.assertRaisesRegex(ValueError, "Revision conflict"):
            self.s.workflow_save("bad", self.graph(), id=item["id"], expected_revision=8)
        changed = self.s.workflow_save("new", self.graph(), id=item["id"], expected_revision=1)
        restored = self.s.workflow_restore(item["id"], changed["revision"], revision=1)
        self.assertEqual(restored["title"], "آزمایش")
        self.assertEqual(restored["revision"], 3)
        self.s.workflow_delete(item["id"], 3)
        self.assertEqual(self.s.workflows(), [])
        self.assertEqual(len(self.s.workflows(deleted=True)), 1)

    def test_reject_api_json_and_bad_cover(self):
        with self.assertRaisesRegex(ValueError, "API prompt"):
            self.save({"1": {"class_type": "KSampler"}})
        with self.assertRaises(ValueError):
            self.s.workflow_save("bad", self.graph(), cover="data:image/svg+xml,<svg/>")

    def test_path_traversal_rejected(self):
        for path in ["../secrets", "unet/../../core.py", str(self.root / "outside")]:
            with self.assertRaises(ValueError):
                inside(self.models, path)
        with self.assertRaises(ValueError):
            self.s.workflow_get("../outside")

    def test_protected_destinations_and_overwrites_rejected(self):
        for p in [self.models / "export", self.output / "backup", self.plugin / "export", self.root]:
            with self.assertRaises(ValueError):
                self.s.destination(str(p))
        existing = self.root / "existing"
        existing.mkdir()
        with self.assertRaises(ValueError):
            self.s.destination(str(existing))

    def test_export_all_empty_dirs_and_verified_model(self):
        model = self.models / "unet" / "model.safetensors"
        model.write_bytes(b"correct-model")
        (self.models / "future" / "empty").mkdir(parents=True)
        item = self.save()
        dest = self.root / "package"
        result = self.job("export", {"id": item["id"], "destination": str(dest)})
        self.assertEqual(result["status"], "complete", result)
        self.assertTrue((dest / "models/future/empty").is_dir())
        for folder in MODEL_FOLDERS:
            self.assertTrue((dest / "models" / folder).is_dir())
        manifest = json.loads((dest / "manifest.json").read_text())
        self.assertTrue(manifest["complete"])
        self.assertEqual(manifest["files"][0]["sha256"], digest(model))
        self.assertNotIn(str(self.root), json.dumps(manifest))

    def test_incomplete_export_requires_explicit_opt_in(self):
        item = self.save()
        options = {"id": item["id"], "destination": str(self.root / "incomplete")}
        self.assertEqual(self.job("export", options)["status"], "failed")
        self.assertFalse((self.root / "incomplete").exists())
        options["allow_incomplete"] = True
        result = self.job("export", options)
        self.assertEqual(result["status"], "complete")
        self.assertFalse(result["result"]["requirements_complete"])

    def test_copy_source_change_and_cancellation(self):
        source = self.output / "image.png"
        source.write_bytes(b"before")
        original = signature(source)
        source.write_bytes(b"after-change")
        with self.assertRaisesRegex(ValueError, "changed"):
            copy_verified(source, self.root / "copy", original)
        def cancel(): raise Cancelled("stop")
        with self.assertRaises(Cancelled):
            copy_verified(source, self.root / "copy2", signature(source), cancel)

    def test_verified_zip_backup_includes_sidecars_and_empty_dirs(self):
        (self.output / "nested" / "empty").mkdir(parents=True)
        (self.output / "nested" / "تصویر.png").write_bytes(b"image")
        (self.output / "metadata.json").write_text('{}')
        (self.output / "unfinished.partial").write_bytes(b"partial")
        dest = self.root / "backup.zip"
        result = self.job("backup", {"destination": str(dest), "zip": True})
        self.assertEqual(result["status"], "complete", result)
        with ZipFile(dest) as z:
            self.assertEqual(z.read("outputs/main/nested/تصویر.png"), b"image")
            self.assertIn("outputs/main/nested/empty/", z.namelist())
            manifest = json.loads(z.read("manifest.json"))
            self.assertIn("unfinished.partial", manifest["exclusions"])
        self.assertTrue((self.output / "metadata.json").exists())

    def test_disk_full_fails_without_success(self):
        (self.output / "a.png").write_bytes(b"image")
        with patch('mtools.service.shutil.disk_usage') as usage:
            usage.return_value.free = 0
            result = self.job("backup", {"destination": str(self.root / "backup")})
        self.assertEqual(result["status"], "failed")

    def test_trash_restore_conflict_purge_and_ownership(self):
        f = self.output / "a.png"
        f.write_bytes(b"image")
        item = self.s.gallery()["files"][0]
        self.assertTrue(self.s.trash([{"id": item["id"], "version": item["signature"]}])[0]["ok"])
        self.assertFalse(f.exists())
        entry = self.s.trash_list()[0]
        self.assertTrue(self.s.uninstall_plan()["blocked"])
        f.write_bytes(b"new")
        with self.assertRaisesRegex(ValueError, "exists"):
            self.s.restore(entry["id"])
        f.unlink()
        self.s.restore(entry["id"])
        self.assertEqual(f.read_bytes(), b"image")
        item = self.s.gallery()["files"][0]
        self.s.trash([{"id": item["id"], "version": item["signature"]}])
        entry = self.s.trash_list()[0]
        with self.assertRaises(ValueError):
            self.s.purge(entry["id"], "yes")
        self.s.purge(entry["id"], "PERMANENTLY DELETE")
        self.assertFalse(self.s.uninstall_plan()["blocked"])

    def test_stale_gallery_selection_rejected(self):
        f = self.output / "a.png"
        f.write_bytes(b"a")
        item = self.s.gallery()["files"][0]
        f.write_bytes(b"modified")
        result = self.s.trash([{"id": item["id"], "version": item["signature"]}])
        self.assertFalse(result[0]["ok"])
        self.assertTrue(f.exists())

    def test_csv_formula_neutralized(self):
        (self.models / "=unsafe").mkdir()
        report = self.s.scan_report()
        csv = self.s.report_export("csv")["text"]
        self.assertIn("'=unsafe", csv)

    def test_unknown_rpc_rejected(self):
        with self.assertRaises(ValueError):
            self.s.call("__dict__", {})

    def test_stdio_protocol_roundtrip_and_shutdown(self):
        test_plugin = self.comfy / "custom_nodes" / "MToolsIPC"
        test_plugin.mkdir()
        shutil.copytree(Path(__file__).resolve().parents[1] / "mtools", test_plugin / "mtools", ignore=shutil.ignore_patterns('__pycache__'))
        requests = [
            {"protocol_version": 1, "request_id": 1, "method": "initialize", "params": {"host": self.host}},
            {"protocol_version": 1, "request_id": 2, "method": "workflow.save", "params": {"title": "تست", "graph": self.graph()}},
            {"protocol_version": 1, "request_id": 3, "method": "workflows", "params": {}},
            {"protocol_version": 1, "request_id": 4, "method": "shutdown", "params": {}}]
        result = subprocess.run([sys.executable, "-B", "-m", "mtools.worker"], cwd=test_plugin,
                                input=''.join(json.dumps(r) + '\n' for r in requests), capture_output=True,
                                text=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([r["request_id"] for r in responses], [1, 2, 3])
        self.assertEqual(responses[2]["result"][0]["title"], "تست")

    def test_embedding_reference_never_claims_complete(self):
        graph = {"nodes": [{"id": 1, "type": "CLIPTextEncode", "widgets_values": ["portrait embedding:style.pt"]}]}
        self.host["nodes"]["CLIPTextEncode"] = {"custom": False}
        report = analyze(graph, self.host)
        self.assertEqual(report["status"], "needs_attention")
        self.assertTrue(report["unresolved"])

    def test_idempotent_job(self):
        a = self.s.call("job.start", {"kind": "scan", "key": "same"})
        b = self.s.call("job.start", {"kind": "scan", "key": "same"})
        self.assertEqual(a, b)

    def test_external_library_owned_and_recorded(self):
        external = self.root / "MyWorkflowLibrary"
        self.s.storage_configure(str(external))
        item = self.save()
        self.assertTrue((external / item["id"] / "1.json").exists())
        self.assertEqual(self.s.uninstall_plan()["external_library"], str(external))
        self.assertTrue((external / ".mtools-owner.json").exists())
        with self.assertRaises(ValueError):
            self.s.storage_configure(str(self.root / "another"))

    def test_offline_uninstall_validates_without_deleting(self):
        if os.name != "nt":
            self.skipTest("Windows cleanup")
        self.s.close()
        script = Path(__file__).resolve().parents[1] / "scripts" / "Cleanup.ps1"
        manifest = self.root / "plan.json"
        manifest.write_text(json.dumps({"product": "MTools", "schema_version": 1, "plugin": str(self.plugin),
                           "comfy": str(self.comfy), "output": str(self.output), "host_pid": None,
                           "installation_id": self.s.owner["installation_id"]}), encoding="utf-8")
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-ManifestPath", str(manifest), "-DryRun"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.plugin.is_dir())
        self.assertIn("No files removed", result.stdout)

    def test_offline_uninstall_rejects_tampered_target(self):
        if os.name != "nt":
            self.skipTest("Windows cleanup")
        script = Path(__file__).resolve().parents[1] / "scripts" / "Cleanup.ps1"
        manifest = self.root / "plan.json"
        manifest.write_text(json.dumps({"product": "MTools", "schema_version": 1, "plugin": str(self.comfy),
                           "comfy": str(self.comfy), "output": str(self.output), "installation_id": "tampered"}), encoding="utf-8")
        result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-ManifestPath", str(manifest), "-DryRun"], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.comfy.is_dir())

    def test_junction_not_followed(self):
        if os.name != "nt":
            self.skipTest("Windows junction fixture")
        target = self.root / "external"
        target.mkdir()
        (target / "secret.txt").write_text("untouched")
        junction = self.models / "junction"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(target)], capture_output=True)
        if result.returncode:
            self.skipTest("Junction creation not available")
        try:
            snapshot = walk(self.models)
            self.assertTrue(any(e["path"] == "junction" for e in snapshot["errors"]))
            self.assertFalse(any('secret' in f["path"] for f in snapshot["files"]))
            with self.assertRaises(ValueError):
                inside(self.models, "junction/secret.txt")
        finally:
            # Only remove the junction itself, never the target directory.
            os.rmdir(junction)


if __name__ == "__main__":
    unittest.main()
