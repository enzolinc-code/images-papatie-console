$ErrorActionPreference='Stop'
$caseRoot=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $caseRoot
if(!(Test-Path -LiteralPath (Join-Path $caseRoot 'config.json'))){Copy-Item -LiteralPath (Join-Path $caseRoot 'config.example.json') -Destination (Join-Path $caseRoot 'config.json')}
$caseCfg=Get-Content -LiteralPath (Join-Path $caseRoot 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$casePort=if($caseCfg.port){[int]$caseCfg.port}else{8799}
$caseUrl='http://127.0.0.1:'+$casePort
function Show-CaseError($message){Add-Type -AssemblyName System.Windows.Forms;[System.Windows.Forms.MessageBox]::Show($message,'手机壳工作台')|Out-Null}
try{
    $caseReady=$null
    try{$caseReady=Invoke-RestMethod -Uri ($caseUrl+'/api/state') -TimeoutSec 2}catch{}
    if($caseReady){
        if($caseReady.app -ne 'multi-template-phonecase-studio' -or [IO.Path]::GetFullPath($caseReady.root) -ne [IO.Path]::GetFullPath($caseRoot)){throw '此端口被其他程序占用，请在config.json修改port后重启。'}
        Start-Process $caseUrl
        exit
    }
    $casePython=Join-Path $caseRoot '.venv\Scripts\python.exe'
    if(!(Test-Path -LiteralPath $casePython)){$casePython=$caseCfg.python}
    if(!$casePython -or !(Test-Path -LiteralPath $casePython)){throw '未找到Python。请先运行“安装运行环境.ps1”，或在config.json设置本机python路径。'}
    & $casePython -B -c 'import PIL,numpy,scipy' 2>$null
    if($LASTEXITCODE -ne 0){throw '图片处理运行库不完整，请先运行“安装运行环境.ps1”。'}
    $caseRuntime=Join-Path $caseRoot 'data\runtime';New-Item -ItemType Directory -Path $caseRuntime -Force|Out-Null
    $env:TEMP=$caseRuntime;$env:TMP=$caseRuntime;$env:PYTHONDONTWRITEBYTECODE='1'
    Start-Process -FilePath $casePython -ArgumentList @('-B','-X','utf8',('"'+(Join-Path $caseRoot 'server.py')+'"')) -WorkingDirectory $caseRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $caseRuntime 'server.out.log') -RedirectStandardError (Join-Path $caseRuntime 'server.err.log')
    for($caseTry=0;$caseTry -lt 30;$caseTry++){
        try{$caseReady=Invoke-RestMethod -Uri ($caseUrl+'/api/state') -TimeoutSec 2}catch{$caseReady=$null}
        if($caseReady -and $caseReady.app -eq 'multi-template-phonecase-studio' -and [IO.Path]::GetFullPath($caseReady.root) -eq [IO.Path]::GetFullPath($caseRoot)){Start-Process $caseUrl;exit}
        Start-Sleep -Milliseconds 500
    }
    throw '服务未启动成功，请查看data\runtime\server.err.log；本入口不会停止其他工作台。'
}catch{Show-CaseError $_.Exception.Message;exit 1}