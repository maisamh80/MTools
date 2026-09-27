# Test installation — <test-portable>

Installed with user authorization on 2026-09-26 into `<test-portable>\ComfyUI\custom_nodes\MTools`.

- Host: ComfyUI 0.34.0; frontend: 1.51.10.
- Private worker: CPython 3.13.15 embeddable x64, checksum-verified archive, local to M Tools.
- Corrected Windows embeddable `_pth` path to `..\..\`; verified import resolves to MTools, not its runtime parent.
- Corrected new-tab activation to use `app.loadGraphData(graph, true, true, newTab)`. The workflow store's `openWorkflow` alone changes the active tab but does not configure the canvas graph on this frontend.
- Live checks passed: worker startup, model inventory (27 categories / 63 files), gallery inventory (370 files), workflow save/read/requirements, new-tab graph contents and preservation of prior tabs, Settings credit, local-only request protection, exact HTTP 206 media byte range, verified selected backup, synthetic-file trash/restore.
- No model inference, real output deletion or real uninstall performed. Destructive file tests used a new synthetic PNG which was removed afterwards. The test workflow is in library recovery.
- Four procedural cover placeholders are retained as the default whenever no uploaded cover is present.
- Settings footer: `Design by Maisam Hosaini | storyeco.xyz`, linking to `https://storyeco.xyz`.

Initial checks used a local server on port 8197 with only M Tools enabled. Existing launcher scripts were not changed. The later correction below establishes the sidebar shortcut; the `?mtools=1` link remains optional.

The host was then restarted with its normal custom nodes enabled. M Tools import, deep-link opening, Settings and private-worker status passed with no browser page errors. The host's 177 installed package metadata directory names/versions were unchanged across that restart. ComfyUI-Manager ran its existing startup/cache update behavior. Two other custom nodes failed to import: Crystools (`deepdiff` missing) and Trellis2 (`pymeshlab` missing); no repair or package installation was attempted for them.

The test server is available at `http://127.0.0.1:8197/?mtools=1` while that process remains running. Normal launcher scripts continue to use their original configuration/port. No shared/core source file or launcher was edited.


## User-feedback correction — 2026-09-26

- Official M Tools sidebar button is visually below Templates; tested twice reopening the overlay without a query string.
- Preserved all four procedural covers; removed their text overlay in cards and details.
- Zero-byte Comfy `put_*_here` markers do not count as models. Empty categories remain visible, gray and non-expandable. Nonempty files, including configurations, are retained. File headings use basenames; absolute paths remain underneath. Output-loader roots no longer appear as external models.
- Export preflight recognizes the built-in, file-free ModelSamplingAuraFlow patch. The user's saved workflow now reports complete requirements. Unknown loaders remain explicit; no silent incomplete export.
- Windows destination picker added for folder/ZIP export. Preview tests verify button/result wiring; PowerShell syntax checked. Native interactive selection still needs the user's manual click-through. JSON uses browser download.
- Nanosecond timestamps and Windows file IDs use decimal strings across JSON to avoid JavaScript integer rounding. Live browser selected-file backup and permanent deletion passed with a disposable TXT fixture; copied bytes matched and the deleted file remained absent after refresh.
- Gallery deletion removes only the matching output's history metadata and matching native asset reference, preserving jobs, sibling outputs and duplicate physical files. A focused history test covers matching names in different subfolders and input/output distinction. Existing open native panels may need reopening to refresh their cached list.
- Back up selected moved to the gallery header. Per-card trash action requires a permanent-deletion confirmation. The old bulk move button was removed; existing recovery items can still be restored.
- Bottom progress bar hides on completion/failure/cancellation; success notices expire and notifications can be dismissed.
- 31 Python tests and browser UI regression tests passed. Live sidebar/report/backup/delete/dependency checks passed without page errors. No user model was copied for these tests and no user output was deleted.

## Destination chooser follow-up

The Windows Forms chooser could remain invisible while its helper process waited. Replaced it with an in-panel, read-only drive/folder browser served by the private worker. Browse, Up, Drives and direct path entry are available; Use this folder fills a new non-overwriting export destination. No native dialog or PowerShell process is started. The export operation still performs all destination validation. 32 Python tests and the preview browser regression passed. A live browser test exercises actual drive enumeration, folder navigation and destination selection without exporting user models.

The proposed 50-pixel reduction on each side is a screenshot-only preview, not an installed CSS change.
