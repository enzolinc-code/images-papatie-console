"""Channel credentials stay local; model defaults are resolved at task creation."""
from pathlib import Path
import os,json
SUPPORTED=('3','4','5')
KEY_NAMES={'3':'CODEX_API_KEY','4':'CHANNEL4_API_KEY','5':'IMG4_API_KEY'}
def user_env(name):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as k:
            value=winreg.QueryValueEx(k,name)[0]
            if value:return str(value)
    except (OSError,ImportError):pass
    return os.environ.get(name,'')
def key(channel):return user_env(KEY_NAMES.get(str(channel),'__NO_CHANNEL__')) if str(channel) in SUPPORTED else ''
def settings(cfg):
    path=cfg.get('channel_settings_path')
    if not path:return {}
    p=Path(path)
    if not p.is_file():raise ValueError('模型配置文件不可用，请检查通道切换器设置')
    try:
        value=json.loads(p.read_text('utf-8-sig'))
        if not isinstance(value,dict):raise ValueError()
        return value
    except (OSError,ValueError) as exc:raise ValueError('模型配置读取失败，请检查通道切换器设置') from exc
def model(channel,cfg):
    channel=str(channel)
    if channel=='3':return cfg['model']
    if channel not in SUPPORTED:raise ValueError('请选择通道3、4或5')
    value=settings(cfg).get('model'+channel) or cfg.get('channel'+channel+'_model') or {'4':'banana-pro','5':'gemini-nano-banana-2.1'}[channel]
    if not isinstance(value,str) or not value.strip() or len(value)>120:raise ValueError('模型名称无效')
    return value

def endpoint(channel,cfg):
    if str(channel)=='3':return cfg['endpoint']
    name,default={'4':('CHANNEL4_API_URL',''),'5':('IMG4_API_URL','')}[str(channel)]
    return user_env(name) or cfg.get('channel'+str(channel)+'_endpoint') or default


class ChannelUnavailable(ValueError):
    stop_batch=True

def http_problem(status,raw=''):
    """Translate a bounded provider error without exposing identifiers or credentials."""
    import re
    text=str(raw)[:10000]
    if status==402 and 'insufficient balance' in text.lower():
        match=re.search(r'current:\s*([0-9.]+)\s*USD,\s*required:\s*([0-9.]+)\s*USD',text,re.I)
        detail=('（当前 $'+match[1]+'，接口要求至少 $'+match[2]+'）') if match else ''
        return {'category':'balance','message':'通道5余额不足'+detail+'，请在Apimart补充余额后再提交；此金额不是单张图片报价。'}
    if status in (401,403):return {'category':'credentials','message':'通道5密钥或访问权限被拒绝（HTTP '+str(status)+'），请检查Apimart账号配置。'}
    if status==402:return {'category':'account','message':'通道5账号请求被拒绝（HTTP 402），请检查Apimart账单与额度。'}
    if status==429:return {'category':'rate_limit','message':'通道5请求受限（HTTP 429），本批后续图片已停止提交，请稍后核实。'}
    return {'category':'request','message':'通道5接口拒绝请求（HTTP '+str(status)+'），请检查所选模型和参数。'}

def preflight(channel,cfg,opener=None):
    """An account-only GET before queueing a new paid channel-5 job."""
    if str(channel)!='5':return
    import urllib.request,urllib.error
    secret=key('5')
    if not secret:raise ChannelUnavailable('通道5未配置密钥')
    proxy=user_env('IMG4_PROXY') or ''
    opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({'http':proxy,'https':proxy}))
    req=urllib.request.Request(endpoint('5',cfg).rstrip('/')+'/models',headers={'Authorization':'Bearer '+secret})
    try:
        with opener.open(req,timeout=12) as r:r.read(1)
    except urllib.error.HTTPError as exc:
        if exc.code==404:return  # A gateway may not implement the optional model directory.
        if exc.code in (400,401,402,403,413,422,429):
            raw=exc.read(10000).decode('utf-8','replace')
            raise ChannelUnavailable(http_problem(exc.code,raw)['message']) from None
        raise ChannelUnavailable('通道5账号检查暂不可用（HTTP '+str(exc.code)+'），尚未提交生图。') from None
    except (OSError,TimeoutError):raise ChannelUnavailable('通道5账号连接检查失败，尚未提交生图，请检查本机代理和网络。') from None
