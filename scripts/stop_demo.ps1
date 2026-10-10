# scripts/stop_demo.ps1 - stop the laptop-side demo processes started by start_demo.ps1.
# Only stops whatever is LISTENING on the demo ports (default 8000 orchestrator, 8501 UI).
# The board app is left running; the port forward is left in place.
param([int]$ApiPort = 8000, [int]$UiPort = 8501)

foreach ($port in @($ApiPort, $UiPort)) {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if (-not $listeners) { Write-Host "port ${port}: nothing running"; continue }
    foreach ($pid_ in ($listeners | Select-Object -ExpandProperty OwningProcess -Unique)) {
        $p = Get-Process -Id $pid_ -ErrorAction SilentlyContinue
        if ($p) {
            Write-Host "port ${port}: stopping $($p.ProcessName) (pid $pid_)"
            Stop-Process -Id $pid_ -Force
        }
    }
}
