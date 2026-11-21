#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Pack', 'Unpack')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$ArchivePath,

    [string]$Root = '',
    [string]$BaseRef = 'origin/master'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }
$rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
$archiveFile = [IO.Path]::GetFullPath($ArchivePath)
$utf8 = New-Object Text.UTF8Encoding($false)

function Get-Hash([byte[]]$Bytes) {
    $hasher = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hasher.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $hasher.Dispose() }
}

function Resolve-EntryPath([string]$Name) {
    if ([string]::IsNullOrWhiteSpace($Name)) { throw 'Empty archive path' }
    foreach ($part in $Name.Split('/')) {
        if ($part -in @('', '.', '..') -or $part -match '[\\<>:"|?*\x00-\x1f]' -or
            $part.EndsWith('.') -or $part.EndsWith(' ') -or
            $part -match '^(?i:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)') {
            throw "Invalid archive path: $Name"
        }
    }
    $target = [IO.Path]::GetFullPath((Join-Path $rootPath $Name))
    if (-not $target.StartsWith($rootPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path outside destination: $Name"
    }
    $current = $target
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            if ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Symbolic link or junction in destination: $current"
            }
        }
        if ($current -eq $rootPath) { break }
        $current = [IO.Path]::GetDirectoryName($current)
    }
    return $target
}

function Test-Included([string]$Name) {
    if ($Name -match '(^|/)(docs?|tests?|testdata|__tests__|e2e|vendor|_vendor|node_modules|portable-source|portable-changes|\.git|\.runtime|\.agents|\.codex|dist|cache|secrets|coverage)(/|$)') { return $false }
    $leaf = ($Name -split '/')[-1]
    if ($leaf -match '(?i)(\.md$|\.rst$|^AGENTS\.|^README|^CHANGELOG|^LICENSE|^test[_-]|^qa[_-]|[_-]test\.|\.tests?\.|\.spec\.|\.testplan\.)') { return $false }
    return $true
}

function Invoke-Git([string[]]$GitArgs) {
    $result = @(& git -C $rootPath -c core.quotepath=false @GitArgs)
    if ($LASTEXITCODE -ne 0) { throw "Git command failed: $($GitArgs -join ' ')" }
    return $result
}

if ($Mode -eq 'Pack') {
    $baseCommit = @(Invoke-Git @('rev-parse', '--verify', "$BaseRef^{commit}"))[0]
    $headCommit = @(Invoke-Git @('rev-parse', 'HEAD'))[0]
    $branch = @(Invoke-Git @('branch', '--show-current'))[0]
    $names = @(
        Invoke-Git @('diff', '--name-only', '--no-renames', $baseCommit, 'HEAD', '--')
        Invoke-Git @('diff', '--name-only', '--no-renames', 'HEAD', '--')
        Invoke-Git @('ls-files', '--others', '--exclude-standard')
    ) | Sort-Object -Unique
    $records = @()
    foreach ($name in $names) {
        if (-not (Test-Included $name)) { continue }
        $file = Resolve-EntryPath $name
        if ($file.Equals($archiveFile, [StringComparison]::OrdinalIgnoreCase)) { continue }
        if (Test-Path -LiteralPath $file -PathType Leaf) {
            $bytes = [IO.File]::ReadAllBytes($file)
            $records += [ordered]@{ path = $name; action = 'write'; sha256 = Get-Hash $bytes; data = [Convert]::ToBase64String($bytes) }
        } elseif (Test-Path -LiteralPath $file) {
            throw "Expected a regular file: $name"
        } else {
            # Do not delete a path that never existed in the selected base.
            & git -C $rootPath cat-file -e "${baseCommit}:$name" 2>$null
            if ($LASTEXITCODE -eq 0) { $records += [ordered]@{ path = $name; action = 'delete' } }
        }
    }
    $package = [ordered]@{
        format = 'platform-installer-branch-changes-v1'
        base = $baseCommit
        head = $headCommit
        branch = $branch
        files = @($records)
    }
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($archiveFile)) | Out-Null
    [IO.File]::WriteAllText($archiveFile, ($package | ConvertTo-Json -Depth 8), $utf8)
    Write-Output "Packed $($records.Count) files into $archiveFile"
    return
}

$package = [IO.File]::ReadAllText($archiveFile, $utf8) | ConvertFrom-Json
if ($package.format -ne 'platform-installer-branch-changes-v1') { throw 'Unsupported archive format' }
$seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$validated = @()
foreach ($record in $package.files) {
    if (-not (Test-Included $record.path)) { throw "Excluded path in archive: $($record.path)" }
    $target = Resolve-EntryPath $record.path
    if (-not $seen.Add($record.path) -or $target.Equals($archiveFile, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Duplicate or conflicting archive path: $($record.path)"
    }
    if (Test-Path -LiteralPath $target -PathType Container) { throw "Directory at file path: $($record.path)" }
    if ($record.action -eq 'write') {
        $bytes = [Convert]::FromBase64String($record.data)
        if ((Get-Hash $bytes) -ne $record.sha256) { throw "Checksum mismatch: $($record.path)" }
        $validated += @{ target = $target; bytes = $bytes; action = 'write' }
    } elseif ($record.action -eq 'delete') {
        $validated += @{ target = $target; action = 'delete' }
    } else { throw "Unsupported operation: $($record.action)" }
}
# Validate the complete archive before overwriting any files.
foreach ($entry in $validated) {
    if ($entry.action -eq 'delete') {
        if (Test-Path -LiteralPath $entry.target) { Remove-Item -LiteralPath $entry.target -Force }
    } else {
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($entry.target)) | Out-Null
        [IO.File]::WriteAllBytes($entry.target, $entry.bytes)
    }
}
Write-Output "Restored $($validated.Count) files into $rootPath"
