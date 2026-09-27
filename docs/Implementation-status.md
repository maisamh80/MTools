# Design v0.3 implementation matrix

Historical design implementation notes; see the repository README for v1.0.0 installation and features. Name/API namespace changed from working name PWL to **M Tools** / `/mtools/v1`; the recovery directory keeps `.pwl-trash` as specified. User-authorized test installation: ComfyUI 0.34.0 / frontend 1.51.10 on the selected Windows Portable copy.

| Area | Source implementation | Remaining acceptance work |
|---|---|---|
| Private worker | Stdlib, isolated executable, stdio protocol, lazy process, clean EOF, single heavy queue | Private runtime passed live; stress cancellation at huge sizes remains |
| UI | Responsive dark cards, gallery, reports, settings, Shadow DOM, supplied icon, offline preview | Further frontend version compatibility testing |
| Sidebar | Official sidebar registration and own-button CSS order; below Templates verified on frontend 1.51.10 | Other frontend versions |
| Report structure | All 27 baseline categories, actual arbitrary/nested/empty folders, files and sidecars | Very large inventories: pagination/virtualization and persistent scan index |
| Report numbers | Logical path bytes, portable/Comfy/models totals, inode-deduplicated bytes, errors | Live scan consistency under heavy generation; not physical allocated disk bytes |
| Model sources | Known `.metadata.json` `source_url` only, HTTPS validation, unknown clearly labeled | Additional metadata formats and manual source URL editor |
| Workflow library | Current tab/import, graph validation, covers, metadata, immutable revisions, soft deletion | Migration UI, historical revision list UI and pruning policy; current recovery accepts revision number |
| Requirements | Known loader adapters, physical path preservation, nested subgraphs, missing/ambiguous/unsupported | More loader fixtures, directory Diffusers adapter, embeddings, explicit manual mappings |
| Custom nodes | Loaded node type/module mapping, safe repo URL, available commit | Missing-node repo attribution, installed package version inspection; local changes reported as unverified |
| Model package | Verified files, all source dirs plus baseline dirs, manifest, metadata, graph, custom-node list, instructions | Input asset collection is report/manual scope; no auto installs |
| Gallery | Effective output root, filters/search/sort, image/video, reveal/open, multi-select | Additional registered roots and virtualization |
| Gallery deletion | Per-card confirmed permanent deletion, exact history/asset-reference cleanup, browser-safe versions; old recovery items remain restorable | Crash journal reconciliation UI and concurrent-writer stress fixtures |
| Output backup | Selected or all independently of filter; files/sidecars/empty dirs; folder/ZIP64; hash verification | >4 GiB real fixture, ZIP partial cleanup/retry UI, post-snapshot changes report |
| Library location | Dedicated external folder before first save, tracked ownership | Migration of populated libraries and UI settings persistence beyond library path |
| Library backup | Current snapshots with metadata/covers/deleted items | All revision history and automatic library restore |
| Uninstall | Plan, offline independent helper, host/worker/reparse/ownership validation, full owned file removal | Direct UI staging, cross-tab broadcast, real final restart inspection |

The implementation uses native JavaScript ES modules instead of introducing a TypeScript/Vue build dependency at this stage. This is an implementation choice; interface behavior and file-safety requirements remain the baseline. No CDN, analytics, AI service or npm production dependency is used.

## File layout

```text
MTools/
  __init__.py             ComfyUI entry point
  bridge.py               host snapshot / local routes / private process
  mtools/
    files.py              bounded paths, no links, verified copy, inventory
    dependencies.py       explicit graph adapters and statuses
    service.py            library, reports, jobs, gallery, ownership
    windows.py            typed Windows shell API
    worker.py             JSON-lines protocol entry point
  web/                    production ES modules, CSS and user icon
  preview/                sample-only interactive preview
  scripts/                private runtime, source archive, offline cleanup
  tests/                  temp-fixture Python tests and browser interactions
  docs/                   design baseline and acceptance status
  runtime/python/         only created during explicit runtime preparation
  data/                   only created when installed worker starts
```

Production RPC is explicit allowlisted dispatch, not arbitrary method execution. File writes require a same-origin nonce and local host. Gallery media is served with aiohttp FileResponse range support. Request/graph size limits are bounded. Source graphs and metadata are untrusted; UI text is escaped and descriptions are never rendered as raw HTML.

## Next integration session

1. User selects a disposable Portable root and frontend version. Record both; do not inspect unrelated installs.
2. Resolve exact Templates placement with that version's supported APIs. A different location is not accepted as completing clause 81.
3. Prepare private runtime in the plugin only; test missing-runtime failure and process lifetime first.
4. Test a graph with unsaved edits, new-tab opening and no execution; check the actual loader widget fixtures.
5. Test output/media range, in-use file handling, real ZIP64 and install/uninstall in that disposable root.
6. Complete the remaining design matrix before calling the release production-ready.
