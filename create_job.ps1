$body = @{
    topic = "Ancient Human Children Daily Life"
    locale = "en-US"
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri 'http://localhost:8000/jobs' -Method Post -ContentType 'application/json' -Body $body
$response | ConvertTo-Json -Depth 10
