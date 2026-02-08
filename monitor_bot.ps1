# monitor_bot.ps1
# Helper script to automatically reconnect SSH and tail logs
# Usage: ./monitor_bot.ps1

$InstanceName = "instance-20260208-161052"
# If you are in a different zone, change this (e.g., us-west1-b)
$Zone = "us-west1-b" 

Write-Host "🔄 Starting Bot Log Monitor..." -ForegroundColor Cyan
Write-Host "   Target: $InstanceName ($Zone)" -ForegroundColor Gray

while ($true) {
    Write-Host "`n🚀 Connecting to Stream Logs..." -ForegroundColor Green
    
    # Run gcloud ssh and execute journalctl
    # This command connects, runs the log tail, and waits. 
    # If the connection drops, the command finishes, and the loop restarts.
    gcloud compute ssh $InstanceName --zone $Zone --command "sudo journalctl -u tradingbot -f -n 50"

    Write-Host "`n⚠️  Connection Lost or Closed." -ForegroundColor Yellow
    Write-Host "⏳ Reconnecting in 3 seconds... (Press Ctrl+C to stop)" -ForegroundColor Cyan
    Start-Sleep -Seconds 3
}
