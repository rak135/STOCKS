param(
    [switch]$NoBrowser,
    [int]$BackendPort = 8787,
    [int]$FrontendPort = 5173,
    [string]$HostAddress = "127.0.0.1",
    [int]$AutoStopAfterSeconds = 0
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontendRoot = Join-Path $projectRoot "ui\frontend"
$logsDir = Join-Path $projectRoot ".logs"
$launcherLog = Join-Path $logsDir "launcher.log"
$backendLog = Join-Path $logsDir "backend.log"
$backendErrLog = Join-Path $logsDir "backend.err.log"
$frontendLog = Join-Path $logsDir "frontend.log"
$frontendErrLog = Join-Path $logsDir "frontend.err.log"

$script:startedProcesses = @()
$script:backendStartedByLauncher = $false
$script:frontendStartedByLauncher = $false

function Write-LauncherLog {
    param([string]$Message)

    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -Path $launcherLog -Value $line
}

function Assert-CommandAvailable {
    param(
        [string]$Command,
        [string]$FriendlyName
    )

    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        throw "$FriendlyName is not available. Install it and retry."
    }
}

function Assert-PythonModules {
    param([string[]]$Modules)

    $importExpr = ($Modules | ForEach-Object { "import $_" }) -join "; "
    py -3 -c $importExpr *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Python dependencies are missing. Run: py -3 -m pip install -r requirements.txt"
    }
}

function Test-TcpPortInUse {
    param([int]$Port)

    return [bool](Get-NetTCPConnection -State Listen -LocalAddress $HostAddress -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Get-FreeTcpPort {
    param([int]$StartPort)

    for ($port = $StartPort; $port -lt ($StartPort + 100); $port++) {
        if (-not (Test-TcpPortInUse -Port $port)) {
            return $port
        }
    }

    throw "Could not find a free TCP port starting at $StartPort"
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 45,
        [int[]]$AcceptStatusCodes = @(200)
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
            if ($AcceptStatusCodes -contains [int]$response.StatusCode) {
                return $true
            }
        }
        catch {
            # keep retrying until timeout
        }

        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)

    return $false
}

function Start-LoggedProcess {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory,
        [string]$StdOutLog,
        [string]$StdErrLog,
        [string]$Name
    )

    $process = Start-Process -FilePath $FilePath `
        -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $StdOutLog `
        -RedirectStandardError $StdErrLog `
        -PassThru

    $script:startedProcesses += [pscustomobject]@{
        Name = $Name
        Process = $process
    }

    return $process
}

function Stop-StartedProcesses {
    foreach ($entry in $script:startedProcesses) {
        $process = $entry.Process
        if ($null -ne $process -and -not $process.HasExited) {
            Write-LauncherLog "Stopping $($entry.Name) (PID $($process.Id))"
            Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
        }
    }
}

try {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
    Set-Content -Path $launcherLog -Value "" -Encoding UTF8

    Write-LauncherLog "Stock Tax one-click launcher starting"
    Write-LauncherLog "Project root: $projectRoot"

    Assert-CommandAvailable -Command "py" -FriendlyName "Python launcher (py)"
    Assert-CommandAvailable -Command "node" -FriendlyName "Node.js"
    Assert-CommandAvailable -Command "npm" -FriendlyName "npm"

    Assert-PythonModules -Modules @("fastapi", "openpyxl", "pydantic")

    $backendStatusUrl = "http://$HostAddress`:$BackendPort/api/status"

    if (Test-TcpPortInUse -Port $BackendPort) {
        Write-LauncherLog "Backend port $BackendPort is already in use. Checking if backend is reusable..."
        if (-not (Wait-HttpReady -Url $backendStatusUrl -TimeoutSeconds 5)) {
            throw "Port $BackendPort is in use, but /api/status is not healthy. Stop the conflicting process and retry."
        }

        Write-LauncherLog "Reusing existing backend on $backendStatusUrl"
    }
    else {
        Write-LauncherLog "Starting backend..."
        $backend = Start-LoggedProcess `
            -FilePath "py" `
            -ArgumentList @("-3", "-m", "stock_tax_app.backend.main") `
            -WorkingDirectory $projectRoot `
            -StdOutLog $backendLog `
            -StdErrLog $backendErrLog `
            -Name "backend"

        $script:backendStartedByLauncher = $true
        Write-LauncherLog "Backend PID: $($backend.Id)"

        if (-not (Wait-HttpReady -Url $backendStatusUrl -TimeoutSeconds 45)) {
            throw "Backend failed to become ready at $backendStatusUrl. See $backendLog and $backendErrLog"
        }
    }

    $nodeModulesPath = Join-Path $frontendRoot "node_modules"
    if (-not (Test-Path $nodeModulesPath)) {
        Write-LauncherLog "node_modules not found. Running npm install once..."
        Set-Location $frontendRoot
        npm install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed. See terminal output."
        }
    }
    else {
        Write-LauncherLog "node_modules present. Skipping npm install."
    }

    $distPath = Join-Path $frontendRoot "dist"
    $needsBuild = $false
    if (-not (Test-Path $distPath)) {
        $needsBuild = $true
    }
    else {
        $distIndex = Join-Path $distPath "index.html"
        if (-not (Test-Path $distIndex)) {
            $needsBuild = $true
        }
        else {
            $latestSrc = Get-ChildItem -Path (Join-Path $frontendRoot "src") -Recurse -File |
                Sort-Object LastWriteTimeUtc -Descending |
                Select-Object -First 1
            $latestDist = Get-ChildItem -Path $distPath -Recurse -File |
                Sort-Object LastWriteTimeUtc -Descending |
                Select-Object -First 1

            if ($null -eq $latestDist -or $latestSrc.LastWriteTimeUtc -gt $latestDist.LastWriteTimeUtc) {
                $needsBuild = $true
            }
        }
    }

    if ($needsBuild) {
        Write-LauncherLog "Frontend dist is missing or stale. Running npm run build..."
        Set-Location $frontendRoot
        npm run build
        if ($LASTEXITCODE -ne 0) {
            throw "npm run build failed. See terminal output."
        }
    }
    else {
        Write-LauncherLog "Frontend dist is up to date."
    }

    # Keep Vite dev for runtime because current frontend relies on /api proxy to backend.
    $frontendPortToUse = if (Test-TcpPortInUse -Port $FrontendPort) {
        Write-LauncherLog "Frontend port $FrontendPort is busy. Choosing a free port..."
        Get-FreeTcpPort -StartPort ($FrontendPort + 1)
    }
    else {
        $FrontendPort
    }

    $frontendUrl = "http://$HostAddress`:$frontendPortToUse"

    if ($frontendPortToUse -eq $FrontendPort -and (Wait-HttpReady -Url $frontendUrl -TimeoutSeconds 2 -AcceptStatusCodes @(200, 304))) {
        Write-LauncherLog "Frontend appears to already be running at $frontendUrl. Reusing it."
    }
    else {
        Write-LauncherLog "Starting frontend dev server on $frontendUrl"
        $viteEntry = Join-Path $frontendRoot "node_modules\vite\bin\vite.js"
        if (-not (Test-Path $viteEntry)) {
            throw "Could not find Vite executable at $viteEntry. Run npm install in ui/frontend."
        }

        $frontend = Start-LoggedProcess `
            -FilePath "node" `
            -ArgumentList @($viteEntry, "--host", $HostAddress, "--port", "$frontendPortToUse", "--strictPort") `
            -WorkingDirectory $frontendRoot `
            -StdOutLog $frontendLog `
            -StdErrLog $frontendErrLog `
            -Name "frontend"

        $script:frontendStartedByLauncher = $true
        Write-LauncherLog "Frontend PID: $($frontend.Id)"

        if (-not (Wait-HttpReady -Url $frontendUrl -TimeoutSeconds 45 -AcceptStatusCodes @(200, 304))) {
            throw "Frontend failed to become ready at $frontendUrl. See $frontendLog and $frontendErrLog"
        }
    }

    Write-LauncherLog ""
    Write-LauncherLog "App is ready"
    Write-LauncherLog "Backend URL: http://$HostAddress`:$BackendPort"
    Write-LauncherLog "Frontend URL: $frontendUrl"
    Write-LauncherLog "Logs:"
    Write-LauncherLog "  launcher: $launcherLog"
    Write-LauncherLog "  backend:  $backendLog"
    Write-LauncherLog "  backend err: $backendErrLog"
    Write-LauncherLog "  frontend: $frontendLog"
    Write-LauncherLog "  frontend err: $frontendErrLog"
    Write-LauncherLog "Press Ctrl+C to stop services started by this launcher."

    if (-not $NoBrowser) {
        Start-Process $frontendUrl
        Write-LauncherLog "Opened browser at $frontendUrl"
    }

    $startedAt = Get-Date
    while ($true) {
        foreach ($entry in $script:startedProcesses) {
            if ($null -ne $entry.Process -and $entry.Process.HasExited) {
                throw "$($entry.Name) process exited unexpectedly with code $($entry.Process.ExitCode). Check logs."
            }
        }

        if ($AutoStopAfterSeconds -gt 0 -and ((Get-Date) - $startedAt).TotalSeconds -ge $AutoStopAfterSeconds) {
            Write-LauncherLog "Auto-stop reached after $AutoStopAfterSeconds seconds."
            break
        }

        Start-Sleep -Seconds 1
    }
}
catch {
    Write-LauncherLog "ERROR: $($_.Exception.Message)"
    Write-Host ""
    Write-Host "Startup failed. See logs in $logsDir" -ForegroundColor Red
    Write-Host "Common fix: py -3 -m pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}
finally {
    Stop-StartedProcesses
    Write-LauncherLog "Launcher exiting"
}
