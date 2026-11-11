param(
    [string]$ComfyRoot = "$env:USERPROFILE\AI\ComfyUI",
    [int]$Port = 8189
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $ComfyRoot).Path
$pythonPath = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw "Missing environment: $pythonPath" }
if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Inspect the existing server before starting another."
}
$logFolder = Join-Path $root 'preview_logs'
New-Item -ItemType Directory -Force -Path $logFolder | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$arguments = @(
    '-u', 'main.py', '--listen', '127.0.0.1', '--port', $Port,
    '--disable-auto-launch', '--disable-all-custom-nodes',
    '--use-pytorch-cross-attention', '--reserve-vram', '2.5',
    '--lowvram', '--cache-none', '--preview-method', 'none', '--disable-comfy-compiler'
)
$process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $root `
    -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logFolder\$stamp.stdout.log" `
    -RedirectStandardError "$logFolder\$stamp.stderr.log"
$record = [ordered]@{
    pid = $process.Id
    executable = $pythonPath
    root = $root
    port = $Port
    arguments = $arguments
    stdout = "$logFolder\$stamp.stdout.log"
    stderr = "$logFolder\$stamp.stderr.log"
}
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath "$logFolder\server.json" -Encoding utf8
$record | ConvertTo-Json -Depth 4
