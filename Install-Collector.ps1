# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 Hackintosh AutoEFI contributors
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z]$')][string]$DriveLetter,
    [string]$ExpectedSerial,
    [UInt64]$ExpectedSize,
    [switch]$ValidatePackageOnly
)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'package'
$manifestPath = Join-Path $PSScriptRoot 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Missing package manifest' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($entry in $manifest.PSObject.Properties) {
    $file = Join-Path $source $entry.Name
    if (-not ([IO.Path]::GetFullPath($file)).StartsWith(([IO.Path]::GetFullPath($source) + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Package path escapes source directory' }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) { throw "Package verification failed: $($entry.Name)" }
}
if ($ValidatePackageOnly) { Write-Output 'PACKAGE_VERIFIED'; return }
if (-not $DriveLetter) { throw 'Specify the USB drive letter with -DriveLetter, without a colon' }
if (-not $ExpectedSerial -or -not $ExpectedSize) { throw 'Specify the expected USB serial number and disk size in bytes; no files written' }
$partition = Get-Partition -DriveLetter $DriveLetter
$disk = $partition | Get-Disk
$volume = Get-Volume -DriveLetter $DriveLetter
if ($disk.BusType -ne 'USB' -or $disk.SerialNumber.Trim() -ne $ExpectedSerial.Trim()) { throw 'USB identity mismatch; no files written' }
if ($disk.Size -ne $ExpectedSize) { throw 'USB size mismatch; no files written' }
if ($volume.FileSystem -ne 'FAT32') { throw 'A FAT32 UEFI USB partition is required. This installer does not format drives.' }
if ($volume.SizeRemaining -lt 1800000000) { throw 'Insufficient free space (need 1.8 GB)' }
$root = $DriveLetter.ToUpperInvariant() + ':\'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$stage = Join-Path $root ('HardwareCollector-stage-' + $stamp)
$active = Join-Path $root 'HardwareCollector'
$backup = Join-Path $root ('HardwareCollector-backup-' + $stamp)
$bootDir = Join-Path $root 'EFI\BOOT'
$boot = Join-Path $bootDir 'BOOTx64.efi'
$bootStage = Join-Path $bootDir ('BOOTx64-collector-stage-' + $stamp + '.efi')
$autorunDir = Join-Path $root 'autorun'
$autorun = Join-Path $autorunDir 'autorun'
$config = Join-Path $root 'EFI\OC\config.plist'
$configBefore = if (Test-Path -LiteralPath $config) { (Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash } else { $null }
foreach ($target in @($stage,$active,$backup,(Join-Path $root 'EFI'),$bootDir,$autorunDir,$boot,$autorun)) {
    $full = [IO.Path]::GetFullPath($target)
    if (-not $full.StartsWith($root,[StringComparison]::OrdinalIgnoreCase) -or $full -eq $root) { throw "Invalid target: $target" }
    if (Test-Path -LiteralPath $target) {
        if ((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point refused: $target" }
    }
}
if ((Test-Path -LiteralPath $stage) -or (Test-Path -LiteralPath $backup)) { throw 'Staging/backup already exists' }
function Write-VerifiedFile([string]$From,[string]$To) {
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($To)) | Out-Null
    $inputFile = [IO.File]::OpenRead($From)
    try {
        $outputFile = [IO.FileStream]::new($To,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None,1048576,[IO.FileOptions]::WriteThrough)
        try { $inputFile.CopyTo($outputFile,1048576); $outputFile.Flush($true) } finally { $outputFile.Dispose() }
    } finally { $inputFile.Dispose() }
    if ((Get-FileHash -LiteralPath $From -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $To -Algorithm SHA256).Hash) { throw "USB readback failed: $To" }
}
[IO.Directory]::CreateDirectory($stage) | Out-Null
foreach ($file in Get-ChildItem -LiteralPath (Join-Path $source 'HardwareCollector') -Recurse -File) {
    $relative = $file.FullName.Substring((Join-Path $source 'HardwareCollector').Length).TrimStart('\')
    Write-VerifiedFile $file.FullName (Join-Path $stage $relative)
}
[IO.Directory]::CreateDirectory($bootDir) | Out-Null
[IO.Directory]::CreateDirectory($backup) | Out-Null
Write-VerifiedFile (Join-Path $source 'EFI\BOOT\BOOTx64.efi') $bootStage
if (Test-Path -LiteralPath $boot) { Write-VerifiedFile $boot (Join-Path $backup 'BOOTx64-original.efi') }
if (Test-Path -LiteralPath $autorun) { Write-VerifiedFile $autorun (Join-Path $backup 'autorun-original') }
$changedActive = $false
$changedAutorun = $false
$changedBoot = $false
try {
    if (Test-Path -LiteralPath $active) { Move-Item -LiteralPath $active -Destination (Join-Path $backup 'HardwareCollector-original') }
    Move-Item -LiteralPath $stage -Destination $active
    $changedActive = $true
    [IO.Directory]::CreateDirectory($autorunDir) | Out-Null
    if (Test-Path -LiteralPath $autorun) { Remove-Item -LiteralPath $autorun }
    $changedAutorun = $true
    Write-VerifiedFile (Join-Path $source 'autorun\autorun') $autorun
    if ($configBefore -and (Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash -ne $configBefore) { throw 'Existing OpenCore config changed unexpectedly' }
    if (Test-Path -LiteralPath $boot) { Remove-Item -LiteralPath $boot }
    Move-Item -LiteralPath $bootStage -Destination $boot
    $changedBoot = $true
    [ordered]@{ disk_serial=$disk.SerialNumber.Trim();disk_model=$disk.FriendlyName;root=$root;backup=$backup;config_sha256=$configBefore;readback='passed';installed=(Get-Date -Format o) } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $backup 'installation.json') -Encoding UTF8
    Write-Output "INSTALLED: $root"
    Write-Output "BACKUP: $backup"
} catch {
    # Restore existing boot files after any failed activation. File removals are
    # literal and non-recursive; the original OC directory is never changed.
    if (Test-Path -LiteralPath (Join-Path $backup 'BOOTx64-original.efi')) {
        if (Test-Path -LiteralPath $boot) { Remove-Item -LiteralPath $boot }
        Write-VerifiedFile (Join-Path $backup 'BOOTx64-original.efi') $boot
    } elseif ($changedBoot -and (Test-Path -LiteralPath $boot)) {
        Remove-Item -LiteralPath $boot
    }
    if (Test-Path -LiteralPath (Join-Path $backup 'autorun-original')) {
        if (Test-Path -LiteralPath $autorun) { Remove-Item -LiteralPath $autorun }
        Write-VerifiedFile (Join-Path $backup 'autorun-original') $autorun
    } elseif ($changedAutorun -and (Test-Path -LiteralPath $autorun)) {
        Remove-Item -LiteralPath $autorun
    }
    if (Test-Path -LiteralPath (Join-Path $backup 'HardwareCollector-original')) {
        if (Test-Path -LiteralPath $active) {
            $failed = Join-Path $root ('HardwareCollector-failed-' + $stamp)
            if (-not ([IO.Path]::GetFullPath($failed)).StartsWith($root,[StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid rollback target' }
            Move-Item -LiteralPath $active -Destination $failed
        }
        Move-Item -LiteralPath (Join-Path $backup 'HardwareCollector-original') -Destination $active
    }
    throw
}
