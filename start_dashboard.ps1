param(
    [switch]$SkipDaemon
)

& (Join-Path $PSScriptRoot "start.ps1") @PSBoundParameters
