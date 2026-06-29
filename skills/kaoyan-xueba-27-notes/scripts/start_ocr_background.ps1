param(
  [int]$Limit = 0,
  [double]$Scale = 2.0,
  [string]$Log = ""
)

$ErrorActionPreference = "Stop"

$SkillRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WorkspaceRoot = Split-Path -Parent (Split-Path -Parent $SkillRoot)
$Python = Join-Path $WorkspaceRoot ".venv-rapidocr\Scripts\python.exe"
$Script = Join-Path $SkillRoot "scripts\ocr_to_db.py"

if (-not $Log) {
  $LogDir = Join-Path $WorkspaceRoot ".ocr-logs"
  New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
  $Log = Join-Path $LogDir "ocr-background.log"
}
elseif (-not [System.IO.Path]::IsPathRooted($Log)) {
  $Log = Join-Path $WorkspaceRoot $Log
}

$LogDir = Split-Path -Parent $Log
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$ArgumentList = @(
  $Script,
  "--engine", "rapidocr",
  "--scale", "$Scale",
  "--quiet",
  "--log", $Log
)

if ($Limit -gt 0) {
  $ArgumentList += @("--limit", "$Limit")
}

function Quote-CmdArgument([string]$Value) {
  $Escaped = $Value -replace '"', '""'
  return ('"{0}"' -f $Escaped)
}

$StdoutLog = Join-Path $LogDir "ocr-background.stdout.log"
$StderrLog = Join-Path $LogDir "ocr-background.stderr.log"
$CmdFile = Join-Path $LogDir "run-ocr-background.cmd"
$QuotedArgs = @()
foreach ($arg in $ArgumentList) {
  $QuotedArgs += (Quote-CmdArgument $arg)
}
$PythonArgs = [string]::Join(" ", $QuotedArgs)
$QuotedWorkspaceRoot = Quote-CmdArgument $WorkspaceRoot
$QuotedPython = Quote-CmdArgument $Python
$QuotedStdoutLog = Quote-CmdArgument $StdoutLog
$QuotedStderrLog = Quote-CmdArgument $StderrLog
$CmdLines = @(
  "@echo off",
  "chcp 65001 >nul",
  ("cd /d " + $QuotedWorkspaceRoot),
  ($QuotedPython + " " + $PythonArgs + " >> " + $QuotedStdoutLog + " 2>> " + $QuotedStderrLog)
)
Set-Content -LiteralPath $CmdFile -Value $CmdLines -Encoding UTF8

$StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
$StartInfo.FileName = "cmd.exe"
$StartInfo.WorkingDirectory = $WorkspaceRoot
$StartInfo.UseShellExecute = $true
$StartInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$StartInfo.Arguments = "/c " + (Quote-CmdArgument $CmdFile)

$Process = [System.Diagnostics.Process]::new()
$Process.StartInfo = $StartInfo
[void]$Process.Start()

Write-Output "Started OCR background process PID=$($Process.Id)"
Write-Output "Log=$Log"
Write-Output "Stderr=$StderrLog"
