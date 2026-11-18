$ErrorActionPreference='Stop'
$caseRoot=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $caseRoot
$caseTemp=Join-Path $caseRoot 'data\runtime';New-Item -ItemType Directory -Path $caseTemp -Force|Out-Null
$env:TEMP=$caseTemp;$env:TMP=$caseTemp
py -3 -m venv (Join-Path $caseRoot '.venv')
if($LASTEXITCODE -ne 0){throw '请先安装64位Python 3.11或更新版本（需要Windows py启动器）。'}
& (Join-Path $caseRoot '.venv\Scripts\python.exe') -m pip install -r (Join-Path $caseRoot 'requirements.txt')
if($LASTEXITCODE -ne 0){throw '依赖安装失败，请检查网络后重新运行。'}
Write-Host '运行环境已安装，可双击打开手机壳工作台.vbs。'