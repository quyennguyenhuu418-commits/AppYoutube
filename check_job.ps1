# Check job status
param([string]$JobId = "00275087-0966-4028-8350-0796404a0547")

for ($i = 0; $i -lt 60; $i++) {
    Clear-Host
    $response = Invoke-RestMethod -Uri "http://localhost:8000/jobs/$JobId" -Method Get
    
    Write-Host "=== Job Status ===" -ForegroundColor Cyan
    Write-Host "Status: $($response.status)" -ForegroundColor Yellow
    Write-Host "Topic: $($response.topic)"
    Write-Host ""
    
    if ($response.stages) {
        Write-Host "=== Stages ===" -ForegroundColor Green
        foreach ($stage in $response.stages) {
            $color = switch ($stage.status) {
                "completed" { "Green" }
                "failed" { "Red" }
                "in_progress" { "Yellow" }
                default { "White" }
            }
            Write-Host "[$($stage.status)] $($stage.name)" -ForegroundColor $color
            if ($stage.message) {
                Write-Host "  -> $($stage.message)"
            }
        }
    }
    
    if ($response.status -eq "completed" -or $response.status -eq "failed") {
        Write-Host ""
        Write-Host "=== Final Status: $($response.status) ===" -ForegroundColor $(if ($response.status -eq "completed") { "Green" } else { "Red" })
        
        if ($response.artifacts) {
            Write-Host ""
            Write-Host "=== Artifacts ===" -ForegroundColor Cyan
            $response.artifacts | ConvertTo-Json -Depth 5
        }
        
        break
    }
    
    Write-Host ""
    Write-Host "Checking again in 5 seconds... ($($i+1)/60)" -ForegroundColor Gray
    Start-Sleep -Seconds 5
}
