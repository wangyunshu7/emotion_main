param([ValidateSet('Start','Stop','Status')][string]$Action = 'Start')
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$binaryRoot = Join-Path $projectRoot '.tools/node_modules/@embedded-postgres/windows-x64/native/bin'
$dataPath = Join-Path $projectRoot '.runtime/pgdata'
$control = Join-Path $binaryRoot 'pg_ctl.exe'
if (!(Test-Path -LiteralPath $control) -or !(Test-Path -LiteralPath $dataPath)) {
    throw 'Temporary PostgreSQL is unavailable. Use your own PostgreSQL or infra/compose.dev.yml.'
}
switch ($Action) {
    'Start' { & $control -D $dataPath -l (Join-Path $projectRoot '.runtime/postgres.log') -o '-p 55432 -h 127.0.0.1' -w start }
    'Stop' { & $control -D $dataPath -m fast -w stop }
    'Status' { & $control -D $dataPath status }
}
exit $LASTEXITCODE
