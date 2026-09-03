[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetHost,

    [Parameter(Mandatory = $true)]
    [string]$TargetUser,

    [Parameter(Mandatory = $true)]
    [string]$KeyPath,

    [Parameter(Mandatory = $true)]
    [string]$RemoteWorkspace
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$syncScript = Join-Path $PSScriptRoot 'qa-sync.ps1'
$verified = & $syncScript -Verify -VerifyHost $TargetHost -VerifyUser $TargetUser `
    -VerifyKeyPath $KeyPath -VerifyWorkspace $RemoteWorkspace
if ($LASTEXITCODE -ne 0 -or ($verified | Select-Object -Last 1) -ne $RemoteWorkspace) {
    throw "QA synchronization smoke check failed for $RemoteWorkspace"
}
Write-Output "QA source tree smoke check: PASS ($RemoteWorkspace)"
