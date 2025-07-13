# 設定 UTF8 編碼
if (-not ([Console]::OutputEncoding.WebName -eq "utf-8")) {
    Write-Host "改變輸出編碼：utf8"
    $OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
}

# 設定路徑
$logDir = "C:\Users\USER\Desktop\Han\學習\金融策略\分析程式\code"
$today = Get-Date -Format "yyyyMMdd"
$logFile = "log-$today.log"
$logPath = Join-Path $logDir $logFile

# 建立資料夾（用 .NET API）
if (-not ([System.IO.Directory]::Exists($logDir))) {
    Write-Host "建立log資料夾： $logDir"
    [System.IO.Directory]::CreateDirectory($logDir) | Out-Null
}

# 建立空的 log 檔案（如果不存在）
if (-not ([System.IO.File]::Exists($logPath))) {
    Write-Host "建立log檔案： $logPath"
    [System.IO.File]::WriteAllText($logPath, "")
}

# 執行 Python 並記錄 log
$pyScript = Join-Path $logDir "momentumNew.py"
python -u $pyScript 2>&1 | Tee-Object -FilePath $logPath -Append
