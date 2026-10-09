param([switch]$OpenBrowser)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskUrl = 'http://127.0.0.1:8093'
$taskPython = Join-Path (Split-Path -Parent $taskRoot) 'hackathon-env\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    $taskPython = Join-Path $taskRoot 'runtime\audit-env\Scripts\python.exe'
}
$taskRuntime = Join-Path $taskRoot 'runtime'
function Test-LocalSite {
    try {
        $taskResponse = Invoke-RestMethod "$taskUrl/api/health" -TimeoutSec 2
        return ($taskResponse.accounts -eq $true -and $taskResponse.storage -eq $true)
    } catch { return $false }
}
$taskEnvPath = Join-Path $taskRoot '.env.production'
if (Test-Path -LiteralPath $taskEnvPath) {
    foreach ($taskLine in Get-Content -LiteralPath $taskEnvPath) {
        if ($taskLine -match '^\s*(SOUNDTRACE_[A-Z0-9_]+)\s*=(.*)$') {
            $taskEnvName = $Matches[1]
            $taskEnvValue = $Matches[2].Trim().Trim([char]34).Trim([char]39)
            if ($taskEnvName -ne 'SOUNDTRACE_PUBLIC_URL' -and $taskEnvName -ne 'SOUNDTRACE_DOMAIN') {
                [Environment]::SetEnvironmentVariable($taskEnvName, $taskEnvValue, 'Process')
            }
        }
    }
}
if (-not (Test-LocalSite)) {
    if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Python environment missing: hackathon-env or runtime\audit-env. Install requirements-public.txt in a local Python environment.' }
    New-Item -ItemType Directory -Path $taskRuntime -Force | Out-Null
    $taskProcess = Start-Process -FilePath $taskPython -ArgumentList @('-m','uvicorn','soundtrace_public:app','--host','127.0.0.1','--port','8093') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskRuntime 'local-site.out.log') -RedirectStandardError (Join-Path $taskRuntime 'local-site.err.log')
    $taskReady = $false
    for ($taskAttempt=0; $taskAttempt -lt 30; $taskAttempt++) {
        if (Test-LocalSite) { $taskReady = $true; break }
        if ($taskProcess.HasExited) { break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $taskReady) { throw "Website failed to start. Check $taskRuntime\local-site.err.log" }
}
Write-Output "SoundTrace ready: $taskUrl"
if ($OpenBrowser) { Start-Process $taskUrl }
