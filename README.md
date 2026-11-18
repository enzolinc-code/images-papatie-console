# 趴趴立牌工作台 · 最新本地部署版

仓库根目录是趴趴立牌工作台；[手机壳工作台](phonecase-studio/)是独立子项目，请进入对应目录安装。

## 本次同步的功能

- 生图通道3、4、5可选，任务固定通道和模型，不自动切换。
- 姿势库：14个常用、6个进阶及原有24个姿势，每页8项，分组选择、动作说明。
- 脸部朝向选项，可要求正脸直视并提供同人物正脸参考；生成相似度和动作仍需人工检查。
- 批量场景默认多图生成，可选择先生成1张样图，满意后继续剩余。
- 素材星标、标签、搜索、原始透明PNG下载、统一删除和回收站。
- 抠图与原动作高清重构独立功能，已有透明素材可复用。
- 任务中心按创建时间展示、突出进行中任务；成品库按时间整理，支持修复和分发。

## Windows安装

需要完整的64位Python，推荐3.11。下载仓库ZIP解压后，在根目录双击`安装.cmd`，安装完成双击`启动工作台.vbs`。也可执行：

```powershell
python setup.py
.venv\Scripts\python.exe launch.py
```

默认网页地址 `http://127.0.0.1:8796/`。Python安装及依赖下载需要网络，程序只监听本机地址。

## 配置自己的生图接口

安装时从config.example.json创建本机config.json，复制.env.example为.env，再在本机填写各通道的API地址、模型与密钥。本仓库不提供真实API地址、密钥、代理设置、账号额度或本机运行路径。

通道3配置endpoint/model；通道4配置channel4_endpoint/channel4_model；通道5配置channel5_endpoint/channel5_model。环境变量名见.env.example。接口需符合相应适配器协议；是否可用及费用由接口服务商决定。本机模型默认值不代表账号已经开通。

用户密钥只在后端读取，不能写进HTML或提交GitHub。没有接口配置时仍可浏览页面，生图需完成本机配置。

## 可选抠图

需要BiRefNet HR和PyMatting时执行 `python setup.py --matting`。从有权使用的来源获取模型，放到runtime/matting，或在本机config.json配置matting_runtime；仓库不含模型权重。详见[BiRefNet](https://github.com/ZhengPeng7/BiRefNet)、[PyMatting](https://github.com/pymatting/pymatting)。

## 更新与数据

升级前备份config.json、.env、data和成品，等待任务结束后替换源码，不要覆盖自己的配置和数据。任务运行中不强制重启。

任务、个人素材、成品、日志、模型、运行环境和密钥不随源码上传。分发目录衔接参考integrations目录，其他电脑需自行部署相应分发服务。

AI可能改变手指、脸部、姿势或材质，锁定提示词不等于自动质检，必须检查后使用。内置动作参考只用于界面提示，详细来源与使用条件见THIRD_PARTY.md。
