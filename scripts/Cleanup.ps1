[CmdletBinding()]
param([string]$ManifestPath, [hashtable]$Plan, [switch]$DryRun)
$ErrorActionPreference = 'Stop'
function Assert-NoReparse([string]$Path) {
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Reparse point rejected: $cursor" }
        $parent = [IO.Directory]::GetParent($cursor)
        if (-not $parent) { break }
        $cursor = $parent.FullName
    }
}
function Assert-Tree([string]$Root) {
    Assert-NoReparse $Root
    foreach ($item in Get-ChildItem -LiteralPath $Root -Force) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point inside owned tree: $($item.FullName)" }
        if ($item.PSIsContainer) { Assert-Tree $item.FullName }
    }
}
if ($ManifestPath) {
    Assert-NoReparse $ManifestPath
    $raw = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    $Plan = @{}
    foreach ($property in $raw.PSObject.Properties) { $Plan[$property.Name] = $property.Value }
}
if (-not $Plan -or $Plan.product -ne 'MTools' -or $Plan.schema_version -ne 1) { throw 'Invalid cleanup plan.' }
$target = [IO.Path]::GetFullPath($Plan.plugin)
Assert-NoReparse $target
$parentDir = [IO.Directory]::GetParent($target)
if ($parentDir.Name -ne 'custom_nodes') { throw 'Target must be a direct child of ComfyUI/custom_nodes.' }
$comfyRoot = [IO.Path]::GetFullPath($Plan.comfy)
if ($parentDir.Parent.FullName -ne $comfyRoot) { throw 'ComfyUI root mismatch.' }
if (-not (Test-Path -LiteralPath (Join-Path ([IO.Directory]::GetParent($comfyRoot).FullName) 'python_embeded'))) { throw 'Portable installation marker missing.' }
if (-not $target.StartsWith($comfyRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Deletion target outside the explicitly named custom_nodes directory.' }
$owner = Get-Content -LiteralPath (Join-Path $target '.mtools-owner.json') -Raw | ConvertFrom-Json
if ($owner.product -ne 'MTools' -or $owner.installation_id -ne $Plan.installation_id) { throw 'Ownership mismatch.' }
if ($Plan.host_pid -and (Get-Process -Id $Plan.host_pid -ErrorAction SilentlyContinue)) { throw 'Close ComfyUI first. The cleaner never closes the host for you.' }
$workerLock = Join-Path $target 'data/worker.lock'
if (Test-Path -LiteralPath $workerLock) {
    $lock = [IO.File]::Open($workerLock, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $lock.Dispose()
}
$trashRoot = [IO.Path]::GetFullPath((Join-Path $Plan.output '.pwl-trash'))
Assert-NoReparse $trashRoot
$removeTrash = $false
if (Test-Path -LiteralPath $trashRoot) {
    $trashOwnerFile = Join-Path $trashRoot '.mtools-owner.json'
    if (-not (Test-Path -LiteralPath $trashOwnerFile)) { throw 'Unowned recovery bin; manual review required.' }
    $trashOwner = Get-Content -LiteralPath $trashOwnerFile -Raw | ConvertFrom-Json
    if ($trashOwner.installation_id -ne $Plan.installation_id) { throw 'Recovery bin ownership mismatch.' }
    $remaining = @(Get-ChildItem -LiteralPath $trashRoot -Force | Where-Object { $_.Name -ne '.mtools-owner.json' })
    if ($remaining.Count) { throw 'Recovery bin is not empty. Restore or explicitly purge its files in M Tools first.' }
    $removeTrash = $true
}
Assert-Tree $target
$externalLibrary = $null
if ($Plan.external_library) {
    $externalLibrary = [IO.Path]::GetFullPath($Plan.external_library)
    Assert-NoReparse $externalLibrary
    if ($externalLibrary -eq [IO.Path]::GetPathRoot($externalLibrary) -or $externalLibrary.StartsWith($comfyRoot, [StringComparison]::OrdinalIgnoreCase) -or $comfyRoot.StartsWith($externalLibrary, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe external library cleanup path.' }
    $externalOwner = Get-Content -LiteralPath (Join-Path $externalLibrary '.mtools-owner.json') -Raw | ConvertFrom-Json
    if ($externalOwner.product -ne 'MTools' -or $externalOwner.installation_id -ne $Plan.installation_id) { throw 'External library ownership mismatch.' }
    Assert-Tree $externalLibrary
}
if ($DryRun) { Write-Output "Validated removal target: $target"; Write-Output 'No files removed.'; return }
Write-Output "This removes ALL M Tools code, private Python and library data: $target"
if ($externalLibrary) { Write-Output "Also removes the owned library folder: $externalLibrary" }
$answer = Read-Host 'Type REMOVE MTOOLS to continue'
if ($answer -cne 'REMOVE MTOOLS') { throw 'Cancelled. Nothing removed.' }
# Revalidate resolved paths immediately before the recursive deletion.
Assert-Tree $target
$ownerAgain = Get-Content -LiteralPath (Join-Path $target '.mtools-owner.json') -Raw | ConvertFrom-Json
if ($ownerAgain.installation_id -ne $Plan.installation_id) { throw 'Ownership changed.' }
if ($removeTrash) {
    Assert-Tree $trashRoot
    $trashEntries = @(Get-ChildItem -LiteralPath $trashRoot -Force)
    if ($trashEntries.Count -ne 1 -or $trashEntries[0].Name -ne '.mtools-owner.json') { throw 'Recovery bin changed.' }
    Remove-Item -LiteralPath $trashRoot -Recurse -Force
}
if ($externalLibrary) {
    Assert-Tree $externalLibrary
    $externalOwner = Get-Content -LiteralPath (Join-Path $externalLibrary '.mtools-owner.json') -Raw | ConvertFrom-Json
    if ($externalOwner.installation_id -ne $Plan.installation_id) { throw 'External library ownership changed.' }
    Remove-Item -LiteralPath $externalLibrary -Recurse -Force
}
Set-Location -LiteralPath ([IO.Path]::GetTempPath())
Remove-Item -LiteralPath $target -Recurse -Force
if (Test-Path -LiteralPath $target) { throw 'Uninstall incomplete: owned folder remains.' }
Write-Output 'Owned files removed. Restart ComfyUI and reload every browser tab to remove the registered menu and loaded frontend code.'
if ($ManifestPath) {
    $helperRoot = [IO.Path]::GetFullPath($PSScriptRoot)
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if (-not $helperRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or (Split-Path $helperRoot -Leaf) -notlike 'MTools-uninstall-*') { throw 'Cannot validate helper cleanup directory.' }
    Assert-Tree $helperRoot
    Remove-Item -LiteralPath $helperRoot -Recurse -Force
}
