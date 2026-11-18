# 本地部署与启动

## 本机已部署

工作台由HTML界面与本地Python服务组成。双击项目里的 `打开手机壳工作台.vbs`，浏览器会打开本地工作台。启动入口会复用同一目录已运行的服务，不会重复启动，也不会停止其他工作台。

默认访问地址为 `http://127.0.0.1:8799/`。这个地址仅在运行工作台的电脑上可访问。

## 在其他Windows电脑部署

1. 从GitHub下载仓库ZIP并解压，进入 `phonecase-studio` 目录。建议放在固定工作目录，文件夹不要只读。
2. 安装64位Python 3.11或更新版本，并确保安装Windows Python启动器 `py`。
3. 在该目录打开PowerShell，执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\安装运行环境.ps1
```

安装脚本会在项目内创建 `.venv` 并联网安装Pillow、NumPy和SciPy。它不会下载生图模型或替你申请付费API。

4. 双击 `打开手机壳工作台.vbs`。首次启动会从 `config.example.json` 生成仅保存在本机的 `config.json`。
5. 不需要AI时，可直接上传刀模及素材，排版后下载透明PNG。

## 可选生图配置

GitHub版本故意不附带真实接口、模型预设、代理或密钥。每条通道应使用与其适配器协议相符的接口，不能只填一个任意网址就认为兼容。

在本机 `config.json` 填写：

- 通道3：`endpoint` 和 `model`。
- 通道4：`channel4_endpoint` 和 `channel4_model`。
- 通道5：`channel5_endpoint` 和 `channel5_model`。

密钥通过Windows用户环境变量填写，变量名分别为 `CODEX_API_KEY`、`CHANNEL4_API_KEY`、`IMG4_API_KEY`。接口地址也可使用相应的API_URL环境变量。不要把密钥写进HTML、README或提交到Git。

通道3及通道4的兼容图片接口分支还需自行安装可信的图片CLI到 `tools/codex-image2-windows-amd64.exe`。仓库不分发该二进制。所用CLI应支持项目调用的edit、image、mask、max-attempts等参数。

修改本机配置后重新打开页面。已有任务固定原模型和接口，不会随配置改写；若服务已有活动任务，先等待结束，避免中断付费请求。

## 文件位置与更新

- `data/jobs`：原图、刀模、排版和任务过程记录。
- `成品`：每个任务的完整图案、透明印刷PNG、白底预览。
- `data/runtime`：运行日志。

上述数据及 `config.json` 不提交GitHub。升级前先备份，等待任务结束后替换源码；保留本机config.json、data、成品及.venv。

## 常见问题

- 找不到Python：先执行安装脚本，确认Python及py启动器可用。
- 端口被占用：在本机config.json修改port再启动，不要直接终止未知程序。
- 页面打不开：双击VBS入口重新启动；查看data/runtime/server.err.log。
- 生图失败：检查对应接口、模型、账号额度、代理与本机密钥。已提交但状态不明时先核对远端任务，不要连续重复提交。

下载的图案保留刀模像素尺寸。送厂前仍需检查毫米规格、出血要求、主体是否被孔洞裁掉，以及AI补图接缝。