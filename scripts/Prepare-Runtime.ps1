# Prepare only M Tools' private runtime. Never pip, PATH changes, registry or Comfy Python.
[CmdletBinding()]
param([string]$Archive)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'runtime-manifest.json') -Raw | ConvertFrom-Json
$runtimeRoot = Join-Path $projectRoot 'runtime'
$runtimeTarget = Join-Path $runtimeRoot 'python'
if (Test-Path -LiteralPath $runtimeTarget) { throw 'Private runtime already exists. It was not changed.' }
foreach ($path in @($projectRoot, $runtimeRoot)) {
    if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Reparse points are not allowed.' }
}
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
$downloadPath = Join-Path $runtimeRoot 'python.download.zip'
$staging = Join-Path $runtimeRoot 'python.partial'
if ((Test-Path -LiteralPath $downloadPath) -or (Test-Path -LiteralPath $staging)) { throw 'Previous preparation files exist. Review them before retrying.' }
if ($Archive) { Copy-Item -LiteralPath $Archive -Destination $downloadPath }
else { Invoke-WebRequest -UseBasicParsing -Uri $manifest.url -OutFile $downloadPath }
if ((Get-FileHash -LiteralPath $downloadPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.sha256) { throw 'Private Python archive checksum mismatch. Nothing executed.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($downloadPath)
try {
    foreach ($entry in $zip.Entries) {
        $resolvedEntry = [IO.Path]::GetFullPath((Join-Path $staging $entry.FullName))
        if (-not $resolvedEntry.StartsWith($staging + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Archive path escapes runtime staging.' }
    }
} finally { $zip.Dispose() }
[IO.Compression.ZipFile]::ExtractToDirectory($downloadPath, $staging)
# Relative to runtime/python: zip standard library, runtime DLLs, then MTools root.
[IO.File]::WriteAllText((Join-Path $staging 'python313._pth'), "python313.zip`n.`n..\..\`n", [Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $staging -Destination $runtimeTarget
Remove-Item -LiteralPath $downloadPath
Write-Output 'Private runtime prepared under MTools/runtime/python. ComfyUI has not been installed or modified.'
