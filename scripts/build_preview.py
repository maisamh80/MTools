"""Create a self-contained, offline preview with in-memory sample data only."""
import base64
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
css = (root / "web/style.css").read_text(encoding="utf-8")
ui = (root / "web/ui.js").read_text(encoding="utf-8")
icon = "data:image/svg+xml;base64," + base64.b64encode((root / "web/MTool.svg").read_bytes()).decode()
ui = ui.replace("const stylesheet = new URL('./style.css', import.meta.url).href;", "const inlineStyle = " + json.dumps(css) + ";")
ui = ui.replace("const logo = new URL('./MTool.svg', import.meta.url).href;", "const logo = " + json.dumps(icon) + ";")
ui = ui.replace('<link rel="stylesheet" href="${stylesheet}">', '<style>${inlineStyle}</style>')
placeholders = ['lavender', 'amber', 'mint', 'arctic']
images = ['data:image/png;base64,' + base64.b64encode((root / f'web/placeholders/{name}.png').read_bytes()).decode() for name in placeholders]
ui = ui.replace('const placeholderImages = placeholderNames.map(name => new URL(`./placeholders/${name}.png`, import.meta.url).href);', 'const placeholderImages = ' + json.dumps(images) + ';')
ui = ui.replace("export const bytes", "const bytes").replace("export async function mount", "async function mount")
project_ui = (root / 'web/projects.js').read_text(encoding='utf-8').replace('export class ProjectPanel', 'class ProjectPanel')
project_images = ['data:image/png;base64,' + base64.b64encode((root / f'web/project-covers/{name}.png').read_bytes()).decode() for name in ['mint','lavender','amber','arctic']]
project_ui = project_ui.replace('const projectCovers=projectCoverNames.map(name=>new URL(`./project-covers/${name}.png`,import.meta.url).href);', 'const projectCovers=' + json.dumps(project_images) + ';')
localization = (root / 'web/i18n.js').read_text(encoding='utf-8').replace('export function ', 'function ')
ui = ui.replace("import {localize} from './i18n.js';", '')
ui = localization + '\n' + project_ui + '\n' + ui.replace("import {ProjectPanel} from './projects.js';", '')

demo = (root / "preview/demo.js").read_text(encoding="utf-8").replace("import {mount} from '../web/ui.js';", "")
html = (root / "preview/index.html").read_text(encoding="utf-8").replace("../web/MTool.svg", icon)
html = html.replace('<script type="module" src="./demo.js"></script>', '<script type="module">' + ui + '\n' + demo + '</script>')
output = root / "preview/MTools-Preview.html"
output.write_text(html, encoding="utf-8")
print(output)
