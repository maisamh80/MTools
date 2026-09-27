"""Build the Windows x64 copy-only release from a verified official Python ZIP."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('runtime_archive', type=Path)
parser.add_argument('destination', type=Path)
args = parser.parse_args()
manifest = json.loads((root/'scripts/runtime-manifest.json').read_text(encoding='utf-8'))
if hashlib.sha256(args.runtime_archive.read_bytes()).hexdigest() != manifest['sha256']:
    raise SystemExit('Runtime checksum mismatch')
excluded = {'.git', 'data', 'runtime', '__pycache__', 'node_modules', '.mtools-owner.json', 'playwright-report', 'test-results', 'tests', 'preview', 'docs'}
readme = '''M Tools 1.0.0 — Windows x64 / ComfyUI Portable

INSTALL
1. Close ComfyUI.
2. Extract the MTools folder into ComfyUI/custom_nodes.
3. Verify ComfyUI/custom_nodes/MTools/__init__.py exists (no double MTools folder).
4. Start ComfyUI normally. Open M Tools below Templates. Refresh browser with Ctrl+F5 if needed.
5. Choose Settings > Language > English / فارسی.

Python 3.13.15 embeddable x64 is included in runtime/python. No Python installation, pip, PowerShell setup command or internet download is required for M Tools. ComfyUI itself must already be installed and working. Do not run Prepare-Runtime.ps1 for this full package.

For an update, keep your existing data folder, ownership marker and independent Projects archives. Do not uninstall to update. Back up your library first.

This package contains no personal library, projects, settings or models. The Python license is preserved at runtime/python/LICENSE.txt. The pinned runtime source and checksum are in scripts/runtime-manifest.json.
'''
fa = '''M Tools 1.0.0 — بستهٔ کامل ویندوز ۶۴بیتی

۱. ComfyUI را ببندید.
۲. پوشهٔ MTools داخل ZIP را در ComfyUI/custom_nodes کپی کنید.
۳. مسیر نهایی باید ComfyUI/custom_nodes/MTools/__init__.py باشد؛ پوشهٔ تودرتوی MTools نسازید.
۴. ComfyUI را به روش معمول اجرا کنید. آیکون M Tools زیر Templates است. در صورت نیاز Ctrl+F5 بزنید.
۵. زبان را از Settings → Language تغییر دهید.

پایتون مستقل داخل بسته است. نصب پایتون، اجرای دستور آماده‌سازی، pip یا دانلود اینترنتی برای افزونه لازم نیست. خود ComfyUI باید قبلاً نصب و قابل اجرا باشد.

برای به‌روزرسانی، پوشهٔ data و فایل مالکیت نصب قبلی را حفظ کنید. برای ارتقا افزونه را uninstall نکنید. ابتدا از کتابخانه پشتیبان بگیرید. آرشیو مستقل پروژه‌ها را حفظ کنید.

بسته فاقد داده‌های شخصی، مدل‌ها و پروژه‌های کاربر است. فایل مجوز پایتون داخل runtime/python/LICENSE.txt نگهداری شده است.
'''
with ZipFile(args.runtime_archive) as runtime, ZipFile(args.destination, 'x', ZIP_DEFLATED) as output:
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root)
        if p.is_file() and not set(rel.parts)&excluded and p.suffix!='.pyc' and rel.as_posix() not in {'README.md','README.fa.md','BILINGUAL-EDITION.md'}:
            output.write(p, 'MTools/'+rel.as_posix())
    for item in runtime.infolist():
        name = PurePosixPath(item.filename)
        if name.is_absolute() or '..' in name.parts or '\\' in item.filename:
            raise ValueError('Unsafe runtime archive path')
        if item.is_dir(): continue
        content = runtime.read(item)
        if item.filename=='python313._pth': content=b'python313.zip\n.\n..\\..\\\n'
        output.writestr('MTools/runtime/python/'+item.filename, content)
    output.writestr('MTools/README.md',readme)
    output.writestr('MTools/README.fa.md',fa)
sha=hashlib.sha256(args.destination.read_bytes()).hexdigest()
args.destination.with_suffix('.zip.sha256').write_text(sha+'  '+args.destination.name+'\n')
print(args.destination)
