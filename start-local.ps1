param(
    [switch]$Run,
    [switch]$HostedWorkerStopped
)

$ErrorActionPreference = 'Stop'
$settingsPath = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path -LiteralPath $settingsPath)) {
    throw 'The local .env file is missing.'
}
foreach ($settingsLine in Get-Content -LiteralPath $settingsPath) {
    $entry = $settingsLine.Trim()
    if (-not $entry -or $entry.StartsWith('#')) { continue }
    $separator = $entry.IndexOf('=')
    if ($separator -lt 1) { throw 'An environment-file line is missing its KEY=VALUE separator.' }
    $settingName = $entry.Substring(0, $separator).Trim()
    if ($settingName -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') { throw 'An environment-file key is invalid.' }
    $settingValue = $entry.Substring($separator + 1).Trim()
    if ($settingValue.Length -ge 2 -and (
        ($settingValue.StartsWith('"') -and $settingValue.EndsWith('"')) -or
        ($settingValue.StartsWith("'") -and $settingValue.EndsWith("'")))) {
        $settingValue = $settingValue.Substring(1, $settingValue.Length - 2)
    }
    [Environment]::SetEnvironmentVariable($settingName, $settingValue, 'Process')
}

$requiredSettings = @('APOLLO_API_KEY', 'BRAVE_SEARCH_API_KEY', 'GEMINI_API_KEY',
    'DATABASE_URL', 'VOXEL1_AUTH_USER', 'VOXEL1_AUTH_PASSWORD')
$missingSettings = @($requiredSettings | Where-Object {
    [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_, 'Process'))
})
if ($missingSettings.Count) {
    Write-Host ('Fill these values in .env: ' + ($missingSettings -join ', '))
    Write-Host 'No server started. No database or provider calls were made.'
    exit 1
}
Write-Host 'Required values are present. Connection validity has not been tested.'
if (-not $Run) {
    Write-Host 'Configuration check only. No server started and no network calls were made.'
    exit 0
}
if (-not $HostedWorkerStopped) {
    throw 'Stop the hosted worker before starting locally against the shared database, then use -Run -HostedWorkerStopped. Pausing a service in the app also pauses the local worker; it does not stop only the hosted worker.'
}
Push-Location $PSScriptRoot
try {
    python server.py
    if ($LASTEXITCODE -ne 0) { throw 'The local server exited with an error.' }
} finally {
    Pop-Location
}
