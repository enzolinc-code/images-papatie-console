# 趴趴立牌工作台 · Papapai Studio

上传人物照片生成上半身趴趴立牌；将透明 PNG 批量放进场景。全部在本地网页操作，不需要通过命令行制作图片。

![八种姿势](docs/poses-preview.jpg)

## 功能

- 8种统一素体姿势卡：托腮垂手、双手托腮、双手搭边、单手比心、搭边挥手、交叠搭臂、侧倾伏靠、侧枕手臂。
- 通道3 / 通道4分别配置密钥，创建任务时固定通道，不自动切换。
- BiRefNet HR + PyMatting 可选抠图：发丝软蒙版与边缘前景色恢复。
- 场景标定与本地保真合成：对透明人物整体做透视和合成，避免AI重新画手指和动作；背景先清理再复用。
- AI创意换场景模式、任务历史、逐张验收、成品下载和账号素材分配。

## 本地安装

需要完整安装的 Python 3.10 或以上版本（推荐3.11）。无需 Node.js、Codex、Ego 浏览器或另装生图二进制。

Windows：下载/解压项目到自己的工作目录，双击 `安装.cmd`，首次安装会联网下载 Pillow；完成后双击 `启动工作台.vbs`，自动打开本地网页。

macOS/Linux 或手动安装：

```sh
python3 setup.py
.venv/bin/python launch.py
```

Windows手动启动：

```powershell
.venv\Scripts\python.exe launch.py
```

默认网页地址 http://127.0.0.1:8796 。如果端口被现有工作台占用，在本地 `config.json` 修改端口。服务只监听127.0.0.1，不开放公网。

## 配置生图

安装会从 `config.example.json` 创建本地 `config.json`。复制 `.env.example` 为 `.env` 并在本机填写自己的密钥：

- `CODEX_API_KEY`：通道3。
- `CHANNEL4_API_KEY`：通道4。

两者互不回退。接口地址及模型名在 `config.json` 配置；支持标准 OpenAI-compatible Images API：文生图 JSON、图生图 multipart，返回 `data[0].b64_json` 或 HTTPS `url`。接口若只支持私有SSE协议或自定义参数，需按服务商说明调整 `tools/image_api.py`。每张AI图独立计费；本地透视合成不调用生图接口。

源码部署版使用可读的 Python 接口客户端，未捆绑本机专有CLI。客户端已做本地模拟接口测试，未在打包时发起新的付费云端验证。

**本地配置、密钥、上传素材与任务记录都已列入 `.gitignore`，不要手工强行加入Git。**

## 可选：发丝抠图

```sh
python setup.py --matting
```

从你有权使用的模型来源取得 `BiRefNet_HR-matting.onnx`，放到 `runtime/matting/`，或将 `config.json` 的 `matting_runtime` 指向已有模型目录。参考 [BiRefNet](https://github.com/ZhengPeng7/BiRefNet) 与 [PyMatting](https://github.com/pymatting/pymatting)。本包不含大模型，也不擅自下载不明来源权重。未配置模型时，已有透明PNG仍可做本地场景合成；不透明图的自动抠图需要配置此项。

## 场景如何保持手指和动作

在“批量替换场景”中使用保真模式，上传透明立牌、场景图片并标定4个角点与承托位置。涂抹旧立牌区域，得到并确认干净背景后，可以反复复用。最终人物只做整体透视和透明合成，不重新生成人物；透视插值会改变像素采样，并非逐像素拷贝。

## 作为技能调用

将 `skills/papapai-studio` 安装到你的技能目录，或让代理读取其中的 `SKILL.md`。第一次使用告知代理本项目实际位置。技能入口包含姿势图制作、工作台部署与场景合成的必要约束，提示词位于该技能的 `references/pose-prompts.json`。

## 上传 GitHub

本目录就是可上传的源码根目录，包含入口文件、网页、测试、八姿图和技能目录。项目仓库：[enzolinc-code/images-papatie-console](https://github.com/enzolinc-code/images-papatie-console)。上传前运行：

```sh
python scripts/release_check.py
python -m unittest discover -v
```

只上传源码，不上传 `.env`、`config.json`、`.venv`、`data`、`qa`、`runtime`。部署包已排除这些文件，以及个人照片、历史任务、二进制程序、ONNX权重。上传同步时只提交上述源码文件。

## 许可与来源

代码为MIT；姿势图和参考资料的来源及使用范围另见 [THIRD_PARTY.md](THIRD_PARTY.md)，不把代码MIT许可误当成第三方图库图片商用许可。

## 从本仓库安装

```sh
git clone https://github.com/enzolinc-code/images-papatie-console.git
cd images-papatie-console
python setup.py
```

作为Codex技能安装（需要Node.js提供npx）：

```sh
npx skills add https://github.com/enzolinc-code/images-papatie-console --skill papapai-studio -g -a codex
```

技能安装只安装代理说明与姿势提示词；完整网页工作台仍按上面的仓库克隆和本地安装步骤部署。
