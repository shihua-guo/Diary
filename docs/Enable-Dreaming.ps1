<#
.SYNOPSIS
  Enable Claude Code Auto-dream on an offline machine.

.DESCRIPTION
  This script:
    1. removes CLAUDE_CODE_DISABLE_AUTO_MEMORY from ~/.claude/settings.json
    2. sets autoMemoryEnabled=true and autoDreamEnabled=true
    3. injects the tengu_onyx_plover feature flag into ~/.claude.json
    4. optionally removes project .consolidate-lock files so the 24h gate passes

  Tested with Claude Code 2.1.318 / CC Switch 4.0.23 on Windows.
  On an offline machine using a third-party/local endpoint, Claude Code cannot
  download Anthropic feature flags, so step 3 is required.

.PARAMETER MinSessions
  Number of prior sessions required before Dream fires. Default 3.
  Use 1 for a first quick test.

.PARAMETER ResetLock
  Remove every project's memory/.consolidate-lock. Only use when no Dream is running.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\Enable-Dreaming.ps1

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\Enable-Dreaming.ps1 -MinSessions 1 -ResetLock
#>
[CmdletBinding()]
param(
    [int]$MinSessions = 3,
    [switch]$ResetLock,
    [string]$ConfigDir = (Join-Path $HOME '.claude'),
    [string]$GlobalConfig = (Join-Path $HOME '.claude.json')
)

$ErrorActionPreference = 'Stop'

function New-Backup([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $bak = "$Path.bak-dream-$stamp"
    Copy-Item -LiteralPath $Path -Destination $bak -Force
    Write-Host "  backup: $bak"
}

function Read-Json([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    return ($raw | ConvertFrom-Json)
}

function Write-Json([string]$Path, $Object) {
    $json = $Object | ConvertTo-Json -Depth 100
    # Claude Code uses JSON.parse and cannot handle a UTF-8 BOM.
    # PowerShell 5.1's `Set-Content -Encoding UTF8` writes a BOM, so use .NET.
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $json, $utf8NoBom)
}

function Ensure-Object($Object, [string]$Name) {
    $prop = $Object.PSObject.Properties[$Name]
    if ($null -eq $prop) {
        $Object | Add-Member -MemberType NoteProperty -Name $Name -Value ([pscustomobject]@{}) -Force
    }
    elseif ($null -eq $prop.Value) {
        $Object.$Name = [pscustomobject]@{}
    }
}

function Set-Property($Object, [string]$Name, $Value) {
    if ($null -eq $Object.PSObject.Properties[$Name]) {
        $Object | Add-Member -MemberType NoteProperty -Name $Name -Value $Value -Force
    }
    else {
        $Object.$Name = $Value
    }
}

if ($MinSessions -lt 1) { $MinSessions = 1 }

Write-Host "==> settings: $ConfigDir\settings.json"
if (-not (Test-Path -LiteralPath $ConfigDir)) {
    New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
}
$settingsPath = Join-Path $ConfigDir 'settings.json'
New-Backup $settingsPath
$settings = Read-Json $settingsPath
if ($null -eq $settings) { $settings = [pscustomobject]@{} }

Ensure-Object $settings 'env'
$disableProp = $settings.env.PSObject.Properties['CLAUDE_CODE_DISABLE_AUTO_MEMORY']
if ($null -ne $disableProp) {
    $settings.env.PSObject.Properties.Remove('CLAUDE_CODE_DISABLE_AUTO_MEMORY')
    Write-Host '  removed env.CLAUDE_CODE_DISABLE_AUTO_MEMORY'
}
Set-Property $settings 'autoMemoryEnabled' $true
Set-Property $settings 'autoDreamEnabled' $true
Write-Json $settingsPath $settings

Write-Host "==> global config: $GlobalConfig"
New-Backup $GlobalConfig
$global = Read-Json $GlobalConfig
if ($null -eq $global) {
    Write-Warning "  $GlobalConfig not found. Launch claude once to create it, then run this script again."
    $global = [pscustomobject]@{}
}

Ensure-Object $global 'cachedGrowthBookFeatures'
$flag = [pscustomobject]@{
    enabled       = $true
    available     = $true
    minHours      = 24
    minSessions   = $MinSessions
    remoteEnabled = $false
}
Set-Property $global.cachedGrowthBookFeatures 'tengu_onyx_plover' $flag
Write-Json $GlobalConfig $global

$processDisable = [Environment]::GetEnvironmentVariable('CLAUDE_CODE_DISABLE_AUTO_MEMORY', 'Process')
if ($processDisable) {
    Remove-Item Env:\CLAUDE_CODE_DISABLE_AUTO_MEMORY -ErrorAction SilentlyContinue
    Write-Host '  removed CLAUDE_CODE_DISABLE_AUTO_MEMORY from this PowerShell session'
}
foreach ($scope in 'User', 'Machine') {
    $val = [Environment]::GetEnvironmentVariable('CLAUDE_CODE_DISABLE_AUTO_MEMORY', $scope)
    if ($val) {
        Write-Warning "  $scope env var CLAUDE_CODE_DISABLE_AUTO_MEMORY=$val is still set; remove it in System Properties or with setx."
    }
}

if ($ResetLock) {
    $projects = Join-Path $ConfigDir 'projects'
    if (Test-Path -LiteralPath $projects) {
        Get-ChildItem -LiteralPath $projects -Directory | ForEach-Object {
            $lock = Join-Path $_.FullName 'memory\.consolidate-lock'
            if (Test-Path -LiteralPath $lock) {
                Remove-Item -LiteralPath $lock -Force
                Write-Host "  removed lock: $lock"
            }
        }
    }
}

Write-Host ''
Write-Host '==> current state'
$s = Read-Json $settingsPath
$g = Read-Json $GlobalConfig
$f = $g.cachedGrowthBookFeatures.tengu_onyx_plover
Write-Host ("  autoMemoryEnabled : {0}" -f $s.autoMemoryEnabled)
Write-Host ("  autoDreamEnabled  : {0}" -f $s.autoDreamEnabled)
Write-Host ("  disable env key   : {0}" -f [bool]$s.env.CLAUDE_CODE_DISABLE_AUTO_MEMORY)
Write-Host ("  onyx flag         : enabled={0} available={1} minHours={2} minSessions={3}" -f $f.enabled, $f.available, $f.minHours, $f.minSessions)
Write-Host ''
Write-Host 'Done. Fully exit and restart Claude Code.'
Write-Host 'Verify with: claude --debug  (search the log for [autoDream])'
