"""Independent production dossiers: media and JSON, never model or node binaries."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import time
import uuid
import zipfile

from .files import no_links, inside, atomic_json, read_json, signature, copy_verified, digest
from .dependencies import validate_graph

ASSETS = set('.png .jpg .jpeg .webp .gif .bmp .tif .tiff .mp4 .webm .mov .mkv .avi .wav .mp3 .flac .ogg .m4a .aac .glb .gltf .obj .ply .stl .txt .json .csv .pdf'.split())

class Projects:
    def project_root(self):
        value = self.settings.get('project_root')
        if not value:
            raise ValueError('Choose your independent Projects folder first')
        root = no_links(value)
        if read_json(root / '.mtools-projects.json').get('product') != 'MTools Projects':
            raise ValueError('Projects folder marker is missing')
        return root

    def projects_configure(self, destination):
        self.ensure_idle()
        path = no_links(destination)
        protected = [self.plugin, Path(self.host['portable']), Path(self.host['output'])]
        protected += [Path(p) for roots in self.host.get('model_roots', {}).values() for p in roots]
        if not Path(destination).is_absolute() or any(path.is_relative_to(p) or p.is_relative_to(path) for p in protected):
            raise ValueError('Choose an absolute Projects folder outside ComfyUI, models and outputs')
        if path.exists():
            if not path.is_dir() or not (path / '.mtools-projects.json').is_file():
                raise ValueError('Choose a new folder, or an existing M Tools Projects folder')
            if read_json(path / '.mtools-projects.json').get('product') != 'MTools Projects':
                raise ValueError('Invalid Projects folder')
        else:
            path = self.destination(destination)
            path.mkdir()
            atomic_json(path / '.mtools-projects.json', {'product': 'MTools Projects', 'schema_version': 1})
        # This archive is deliberately NOT added to uninstall ownership.
        self.settings['project_root'] = str(path)
        atomic_json(self.data / 'settings.json', self.settings)
        return {'path': str(path)}

    def projects_list(self):
        if not self.settings.get('project_root'):
            return {'root': None, 'items': [], 'errors': []}
        root = self.project_root()
        items, errors = [], []
        for folder in root.iterdir():
            if re.fullmatch('[0-9a-f]{32}\\.partial', folder.name):
                errors.append({'folder': folder.name, 'error': 'Incomplete operation; partial files retained for review'})
                continue
            if not re.fullmatch('[0-9a-f]{32}', folder.name):
                continue
            try:
                item = self.project_get(folder.name)
                items.append({k: v for k, v in item.items() if k not in {'graph', 'capture', 'files'}} | {'file_count': len(item['files'])})
            except (ValueError, OSError, KeyError) as e:
                errors.append({'folder': folder.name, 'error': str(e)})
        return {'root': str(root), 'items': sorted(items, key=lambda p: p['created_at'], reverse=True), 'errors': errors}

    def project_dir(self, id):
        if not isinstance(id, str) or not re.fullmatch('[0-9a-f]{32}', id):
            raise ValueError('Invalid project id')
        return inside(self.project_root(), id)

    def project_get(self, id):
        folder = self.project_dir(id)
        item = read_json(no_links(folder / 'project.json'))
        if item.get('format') != 'mtools-project' or item.get('schema_version') != 1:
            raise ValueError('Unsupported project format')
        item['id'] = id
        item['graph'] = read_json(no_links(folder / 'workflow.json'))
        return item

    def project_file(self, id, path):
        item = self.project_get(id)
        allowed = {f['path'] for f in item['files']} | {'workflow.json', 'project.json'}
        if item.get('cover_path'):
            allowed.add(item['cover_path'])
        if path not in allowed:
            raise ValueError('File is not part of this project')
        return {'path': str(inside(self.project_dir(id), path))}

    def project_reveal(self, id):
        from .windows import reveal_file
        reveal_file(self.project_dir(id) / 'project.json')
        return {'opened': True}

    def project_edit(self, id, title, description='', prompt='', cover=None, expected_updated_at=None):
        self.ensure_idle()
        item = self.project_get(id)
        if expected_updated_at != item['updated_at']:
            raise ValueError('Project changed; reopen its details')
        if not str(title).strip() or len(title) > 200 or len(description) > 20000 or len(prompt) > 100000:
            raise ValueError('Invalid title or text is too long')
        item.update(title=title.strip(), description=description, prompt=prompt, updated_at=time.time())
        if cover:
            item['cover_path'] = self.project_cover(self.project_dir(id), cover)
        item.pop('graph', None)
        atomic_json(self.project_dir(id) / 'project.json', item)
        return {'id': id}

    def project_cover(self, folder, cover):
        if not isinstance(cover, str) or not cover.startswith('data:image/png;base64,'):
            raise ValueError('Use a PNG cover')
        data = base64.b64decode(cover.split(',', 1)[1], validate=True)
        if len(data) > 10*1024*1024 or not data.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Invalid cover')
        name = 'cover-' + uuid.uuid4().hex + '.png'
        (folder / name).write_bytes(data)
        return name

    def project_upload(self, token):
        if not isinstance(token, str) or not re.fullmatch('[0-9a-f]{32}', token):
            raise ValueError('Invalid upload')
        path = inside(self.data / 'project-uploads', token)
        if not path.is_file():
            raise ValueError('Upload no longer available; select the file again')
        return path

    def project_job(self, kind, options, job, check):
        if kind == 'project.update':
            return self.project_update(options, job, check)
        if kind == 'project.export':
            return self.project_export(options, job, check)
        root = self.project_root()
        id = uuid.uuid4().hex
        partial = root / (id + '.partial')
        partial.mkdir()
        if kind == 'project.import':
            return self.project_import(options, partial, id, job, check)
        graph = validate_graph(options.get('graph', {'nodes': []}))
        title = str(options.get('title') or 'Untitled project').strip()[:200]
        capture = options.get('capture') or {}
        sources, warnings = [], list(capture.get('warnings', []))
        # Only explicit bridge-discovered input/output-relative paths are read.
        for entry in capture.get('files', []):
            role = entry.get('role')
            if role not in {'references', 'outputs'}:
                continue
            try:
                host_root = self.host['input' if role == 'references' else 'output']
                source = inside(host_root, entry['path'])
                self.project_asset(source)
                sources.append((source, role, source.name))
            except (ValueError, OSError, KeyError) as e:
                warnings.append(f"{entry.get('path')}: {e}")
        for entry in options.get('uploads', []):
            role = entry.get('role')
            if role not in {'references', 'outputs'}:
                raise ValueError('Invalid file role')
            name = Path(entry['name'].replace('\\', '/')).name
            self.project_asset_name(name)
            sources.append((self.project_upload(entry['token']), role, name))
        files, seen = [], set()
        total = sum(signature(p)[0] for p, _, _ in sources)
        if shutil.disk_usage(root).free < total + 16*1024*1024:
            raise ValueError('Not enough space in Projects archive')
        for i, (source, role, name) in enumerate(sources):
            check()
            if (str(source), role) in seen:
                continue
            seen.add((str(source), role))
            target = f'{role}/{len(files)+1:03d}-{name}'
            version = signature(source)
            sha = copy_verified(source, inside(partial, target), version, check)
            files.append({'path': target, 'name': name, 'role': role, 'size': version[0], 'sha256': sha})
            job['progress'] = (i+1)/max(1, len(sources))*.9
        atomic_json(partial / 'workflow.json', graph)
        metadata = {'format': 'mtools-project', 'schema_version': 1, 'id': id, 'title': title,
            'description': str(options.get('description', ''))[:20000], 'prompt': str(options.get('prompt', ''))[:100000],
            'created_at': time.time(), 'updated_at': time.time(), 'files': files,
            'bytes': sum(f['size'] for f in files), 'warnings': warnings,
            'capture': capture.get('metadata', {}), 'cover_path': None}
        if options.get('cover'):
            metadata['cover_path'] = self.project_cover(partial, options['cover'])
        atomic_json(partial / 'project.json', metadata)
        check()
        partial.rename(root / id)
        for upload in options.get('uploads', []):
            self.project_upload(upload['token']).unlink(missing_ok=True)
        return {'id': id, 'destination': str(root / id), 'warnings': warnings}

    def project_asset_name(self, name):
        if Path(name).suffix.lower() not in ASSETS:
            raise ValueError('Only reference/output media and data files are allowed; no models, code or executables')

    def project_asset(self, path):
        self.project_asset_name(path.name)
        if not path.is_file():
            raise ValueError('File not found')

    def project_import(self, options, partial, id, job, check):
        archive = None
        if options.get('token'):
            archive = zipfile.ZipFile(self.project_upload(options['token']))
            entries = archive.infolist()
            if len(entries) > 10000 or sum(e.file_size for e in entries) > 100*1024**3:
                archive.close()
                raise ValueError('Project archive exceeds import limits')
            names = [e.filename for e in entries]
            if len(names) != len(set(names)):
                archive.close()
                raise ValueError('Duplicate archive paths')
            def read(name):
                if archive.getinfo(name).file_size > 24*1024**2:
                    raise ValueError('Project metadata too large')
                return json.loads(archive.read(name))
        else:
            source = no_links(options.get('path', ''))
            def read(name):
                file = inside(source, name)
                if file.stat().st_size > 24*1024**2:
                    raise ValueError('Project metadata too large')
                return read_json(file)
        try:
            item = read('project.json')
            if item.get('format') != 'mtools-project' or item.get('schema_version') != 1:
                raise ValueError('Select a M Tools project folder or ZIP with project.json at its root')
            graph = validate_graph(read('workflow.json'))
            files = item.get('files', [])
            if not isinstance(item.get('title'), str) or not isinstance(item.get('created_at'), (int, float)) or not isinstance(files, list):
                raise ValueError('Invalid project metadata')
            for file in files:
                if not isinstance(file, dict) or not isinstance(file.get('size'), int) or file['size'] < 0 or not re.fullmatch('[0-9a-f]{64}', str(file.get('sha256', ''))):
                    raise ValueError('Invalid project file size or checksum')
            names = [f['path'] for f in files]
            if len(names) != len(set(names)) or len(names) > 10000:
                raise ValueError('Invalid project file list')
            total = sum(f['size'] for f in files)
            if total < 0 or shutil.disk_usage(partial).free < total + 16*1024**2:
                raise ValueError('Insufficient space or invalid project sizes')
            copy_list = list(files)
            if item.get('cover_path'):
                if not re.fullmatch(r'cover-[0-9a-f]{32}\.png', item['cover_path']):
                    raise ValueError('Invalid cover path')
                copy_list.append({'path': item['cover_path']})
            for i, file in enumerate(copy_list):
                check()
                name = file['path']
                target = inside(partial, name)
                if name != item.get('cover_path'):
                    if file.get('role') not in {'references', 'outputs'} or not name.startswith(file['role'] + '/'):
                        raise ValueError('Invalid media path')
                    self.project_asset_name(name)
                if archive:
                    info = archive.getinfo(name)
                    if (info.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError('Archive links are not allowed')
                    if file.get('size', info.file_size) != info.file_size:
                        raise ValueError('File size mismatch')
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(name) as src, target.open('xb') as dst:
                        while block := src.read(4*1024**2):
                            check()
                            dst.write(block)
                    sha = digest(target, check)
                else:
                    src = inside(source, name)
                    sha = copy_verified(src, target, signature(src), check)
                if file.get('sha256') and sha != file['sha256']:
                    raise ValueError('Project file integrity check failed: ' + name)
                if name != item.get('cover_path'):
                    file.update(size=target.stat().st_size, sha256=sha)
                job['progress'] = (i+1)/max(1,len(copy_list))*.9
            item.update(id=id, imported_at=time.time(), updated_at=time.time(), files=files, bytes=sum(f['size'] for f in files))
            atomic_json(partial / 'workflow.json', graph)
            atomic_json(partial / 'project.json', item)
            check()
            partial.rename(self.project_root() / id)
            return {'id': id, 'destination': str(self.project_root() / id)}
        finally:
            if archive:
                archive.close()

    def project_export(self, options, job, check):
        item = self.project_get(options['id'])
        folder = self.project_dir(options['id'])
        destination = self.destination(options['destination'])
        root = self.project_root()
        if destination.is_relative_to(root) or root.is_relative_to(destination):
            raise ValueError('Export outside the Projects archive')
        temporary = destination.with_name(destination.name + '.partial')
        paths = ['project.json', 'workflow.json'] + [f['path'] for f in item['files']]
        if item.get('cover_path'):
            paths.append(item['cover_path'])
        total = sum(inside(folder, name).stat().st_size for name in paths)
        if shutil.disk_usage(destination.parent).free < total + 16*1024**2:
            raise ValueError('Not enough space for ZIP')
        with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for i, name in enumerate(paths):
                check()
                source = inside(folder, name)
                before = signature(source)
                with source.open('rb') as src, archive.open(name, 'w', force_zip64=True) as dst:
                    while block := src.read(4*1024**2):
                        check()
                        dst.write(block)
                if signature(source) != before:
                    raise ValueError('Project file changed during export')
                job['progress'] = (i+1)/len(paths)*.9
        check()
        if destination.exists():
            raise ValueError('Destination already exists')
        temporary.rename(destination)
        return {'destination': str(destination)}

    def project_update(self, options, job, check):
        id = options['id']
        item = self.project_get(id)
        if options.get('expected_updated_at') != item['updated_at']:
            raise ValueError('Project changed; reopen its details')
        title = str(options.get('title', '')).strip()
        if not title or len(title) > 200:
            raise ValueError('Title is required, up to 200 characters')
        folder = self.project_dir(id)
        uploads = options.get('uploads', [])
        total = sum(self.project_upload(u['token']).stat().st_size for u in uploads)
        if shutil.disk_usage(folder).free < total + 16*1024**2:
            raise ValueError('Not enough archive space')
        for i, upload in enumerate(uploads):
            check()
            role = upload.get('role')
            if role not in {'references', 'outputs'}:
                raise ValueError('Invalid media role')
            name = Path(upload['name'].replace('\\', '/')).name
            self.project_asset_name(name)
            source = self.project_upload(upload['token'])
            target = role + '/' + uuid.uuid4().hex[:12] + '-' + name
            version = signature(source)
            sha = copy_verified(source, inside(folder, target), version, check)
            item['files'].append({'path': target, 'name': name, 'role': role, 'size': version[0], 'sha256': sha, 'added_manually': True})
            job['progress'] = (i+1)/max(1,len(uploads))*.9
        item.update(title=title, description=str(options.get('description',''))[:20000], prompt=str(options.get('prompt',''))[:100000], updated_at=time.time(), bytes=sum(f['size'] for f in item['files']))
        if options.get('cover'):
            item['cover_path'] = self.project_cover(folder, options['cover'])
        item.pop('graph', None)
        check()
        atomic_json(folder / 'project.json', item)
        for upload in uploads:
            self.project_upload(upload['token']).unlink(missing_ok=True)
        return {'id': id, 'destination': str(folder)}
