[CmdletBinding()]
param([ValidateSet('folder','zip')][string]$Mode='folder', [string]$SuggestedName='MTools-export')
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$SuggestedName = [regex]::Replace($SuggestedName, '[<>:"/\\|?*\x00-\x1f]', '_').Trim().TrimEnd('.')
if (-not $SuggestedName) { $SuggestedName='MTools-export' }
$result=$null
if ($Mode -eq 'zip') {
    $dialog=[Windows.Forms.SaveFileDialog]::new()
    $dialog.Title='M Tools - Choose destination'
    $dialog.Filter='ZIP archive (*.zip)|*.zip'
    $dialog.FileName=$SuggestedName+'.zip'
    $dialog.AddExtension=$true
    if ($dialog.ShowDialog() -eq [Windows.Forms.DialogResult]::OK) { $result=$dialog.FileName }
} else {
    $dialog=[Windows.Forms.FolderBrowserDialog]::new()
    $dialog.Description='Choose a parent folder. M Tools creates a new export folder inside it.'
    $dialog.ShowNewFolderButton=$true
    if ($dialog.ShowDialog() -eq [Windows.Forms.DialogResult]::OK) {
        $result=Join-Path $dialog.SelectedPath $SuggestedName
        $index=2
        while (Test-Path -LiteralPath $result) { $result=Join-Path $dialog.SelectedPath ($SuggestedName+'-'+$index); $index++ }
    }
}
$dialog.Dispose()
@{path=$result} | ConvertTo-Json -Compress
