# Validation record — 2026-09-26

The initial source-only checks below were followed by a user-authorized installation on `<test-portable>`. Real runtime and integration results are recorded in [Test-installation.md](Test-installation.md); they supersede the earlier source-only limitations for the checks explicitly listed there.

## Executed

- **31 Python tests passed** on Windows using the available development runtime. Temporary fake Portable folders cover all 27 model categories, unknown/empty folders, Unicode paths, unet/clip physical destinations, missing/ambiguous/dynamic/custom/embedding statuses, nested subgraphs, external-root statuses, JSON validation, revision conflicts/recovery, protected paths and existing destinations, verified model copies, incomplete-package opt-in, source changes, cancellation, output ZIP/sidecars/empty directories, simulated disk-full, trash restore/purge, stale gallery selection, CSV formula neutralization, idempotent jobs, external-library ownership and Windows junction rejection.
- Worker stdio initialize/save/list/shutdown round-trip passed using a copied package in a temporary fake installation. This tests the protocol, **not** the bundled private runtime startup.
- Offline PowerShell cleaner valid-target **dry-run** passed; tampered-target dry-run was rejected. No real uninstall was performed.
- Interactive browser test passed: six sample workflow cards, details/missing-model status, explicit new-tab action, escaped HTML title, 27 report folders, gallery selection/deletion/recovery, uninstall pending state, responsive mobile viewport; no page JavaScript errors.
- JavaScript parse checks and Python compilation passed. PowerShell scripts parsed successfully.
- Desktop screenshots inspected; transitions are allowed to settle before capture.

## Not yet established

No live ComfyUI load/execute test, private CPython 3.13.15 executable smoke test, real media-range transfer, >4 GiB archive, live locked-file/concurrent-writer stress or destructive end-to-end uninstall has run. The tests are not a claim that all design acceptance criteria are complete. Current release gates are listed in `Implementation-status.md`.
