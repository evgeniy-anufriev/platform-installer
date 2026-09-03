[CmdletBinding(DefaultParameterSetName = 'Sync')]
param(
    [Parameter(Mandatory = $true, ParameterSetName = 'Sync')]
    [string]$TargetHost,

    [Parameter(Mandatory = $true, ParameterSetName = 'Sync')]
    [string]$TargetUser,

    [Parameter(Mandatory = $true, ParameterSetName = 'Sync')]
    [string]$KeyPath,

    [Parameter(ParameterSetName = 'Sync')]
    [switch]$IncludeGo,

    [Parameter(Mandatory = $true, ParameterSetName = 'Cleanup')]
    [switch]$Cleanup,

    [Parameter(Mandatory = $true, ParameterSetName = 'Cleanup')]
    [string]$CleanupHost,

    [Parameter(Mandatory = $true, ParameterSetName = 'Cleanup')]
    [string]$CleanupUser,

    [Parameter(Mandatory = $true, ParameterSetName = 'Cleanup')]
    [string]$CleanupKeyPath,

    [Parameter(Mandatory = $true, ParameterSetName = 'Cleanup')]
    [string]$RemoteWorkspace,

    [Parameter(Mandatory = $true, ParameterSetName = 'Verify')]
    [switch]$Verify,

    [Parameter(Mandatory = $true, ParameterSetName = 'Verify')]
    [string]$VerifyHost,

    [Parameter(Mandatory = $true, ParameterSetName = 'Verify')]
    [string]$VerifyUser,

    [Parameter(Mandatory = $true, ParameterSetName = 'Verify')]
    [string]$VerifyKeyPath,

    [Parameter(Mandatory = $true, ParameterSetName = 'Verify')]
    [string]$VerifyWorkspace
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$sourceDirectories = @('ansible-core', 'services', 'examples', 'contracts')
$sourceFiles = @()
if ($IncludeGo) {
    $sourceDirectories += @('cmd', 'internal')
    $sourceFiles += @('go.mod', 'go.sum')
}
$sourceEntries = $sourceDirectories + $sourceFiles

foreach ($sourceDirectory in $sourceDirectories) {
    if (-not (Test-Path -LiteralPath $sourceDirectory -PathType Container)) {
        throw "QA synchronization must be run from the repository root; missing source directory: $sourceDirectory"
    }
}
foreach ($sourceFile in $sourceFiles) {
    if (-not (Test-Path -LiteralPath $sourceFile -PathType Leaf)) {
        throw "QA synchronization must be run from the repository root; missing source file: $sourceFile"
    }
}

function Invoke-Ssh {
    param(
        [string]$HostName,
        [string]$UserName,
        [string]$Identity,
        [string]$Command
    )

    & ssh -o IdentitiesOnly=yes -i $Identity "$UserName@$HostName" $Command
    if ($LASTEXITCODE -ne 0) {
        throw "SSH command failed with exit code $LASTEXITCODE"
    }
}

function Assert-SafeRemotePath {
    param([string]$Path)

    if ($Path -notmatch '^/var/tmp/platform-installer-qa-[a-z0-9-]+$') {
        throw "Remote workspace must be an isolated /var/tmp/platform-installer-qa-* path"
    }
}

function Test-RemoteSourceTree {
    param(
        [string]$HostName,
        [string]$UserName,
        [string]$Identity,
        [string]$Workspace
    )

    Assert-SafeRemotePath -Path $Workspace
    $checks = ($sourceDirectories | ForEach-Object { "test -d '$Workspace/$_'" }) -join ' && '
    $checks += " && test -f '$Workspace/ansible-core/tools/build_fixture_catalog.py'"
    Invoke-Ssh -HostName $HostName -UserName $UserName -Identity $Identity -Command $checks
}

if ($PSCmdlet.ParameterSetName -eq 'Cleanup') {
    Assert-SafeRemotePath -Path $RemoteWorkspace
    Invoke-Ssh -HostName $CleanupHost -UserName $CleanupUser -Identity $CleanupKeyPath -Command "rm -rf '$RemoteWorkspace'"
    exit 0
}

if ($PSCmdlet.ParameterSetName -eq 'Verify') {
    Test-RemoteSourceTree -HostName $VerifyHost -UserName $VerifyUser -Identity $VerifyKeyPath -Workspace $VerifyWorkspace
    Write-Output $VerifyWorkspace
    exit 0
}

$workspace = "/var/tmp/platform-installer-qa-$([guid]::NewGuid().ToString('N'))"
$remote = "$TargetUser@$TargetHost`:$workspace/"

try {
    Invoke-Ssh -HostName $TargetHost -UserName $TargetUser -Identity $KeyPath -Command "umask 077 && mkdir -p '$workspace'"

    & scp -q -o IdentitiesOnly=yes -i $KeyPath -r -- $sourceEntries $remote
    if ($LASTEXITCODE -ne 0) {
        throw "scp -r failed with exit code $LASTEXITCODE"
    }

    Test-RemoteSourceTree -HostName $TargetHost -UserName $TargetUser -Identity $KeyPath -Workspace $workspace
    Write-Output $workspace
}
catch {
    try {
        Invoke-Ssh -HostName $TargetHost -UserName $TargetUser -Identity $KeyPath -Command "rm -rf '$workspace'"
    }
    catch {
        Write-Error "QA workspace cleanup after transfer failure also failed: $($_.Exception.Message)"
    }
    throw "QA source synchronization failed: $($_.Exception.Message)"
}
