[CmdletBinding()]
param([switch]$DryRun)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$ownerFile = Join-Path $projectRoot '.mtools-owner.json'
if (-not (Test-Path -LiteralPath $ownerFile)) { throw 'No installation marker. Refusing deletion.' }
$owner = Get-Content -LiteralPath $ownerFile -Raw | ConvertFrom-Json
$installFile = Join-Path $projectRoot 'data/installation.json'
if (-not (Test-Path -LiteralPath $installFile)) { throw 'No installation record. Refusing deletion.' }
$installation = Get-Content -LiteralPath $installFile -Raw | ConvertFrom-Json
$manifest = @{ schema_version=1; product='MTools'; plugin=$projectRoot; installation_id=$owner.installation_id; output=$installation.output; host_pid=$installation.host_pid; comfy=$installation.comfy; external_library=$installation.external_library }
if ($DryRun) {
    & (Join-Path $PSScriptRoot 'Cleanup.ps1') -Plan $manifest -DryRun
    return
}
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$helperRoot = Join-Path $tempRoot ('MTools-uninstall-' + [Guid]::NewGuid().ToString('N'))
if (-not $helperRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid helper directory.' }
New-Item -ItemType Directory -Path $helperRoot | Out-Null
$helper = Join-Path $helperRoot 'Cleanup.ps1'
$planFile = Join-Path $helperRoot 'plan.json'
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Cleanup.ps1') -Destination $helper
[IO.File]::WriteAllText($planFile, ($manifest | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
# Synchronous invocation; no background window, no command constructed from paths.
& $helper -ManifestPath $planFile
