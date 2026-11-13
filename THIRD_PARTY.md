# 第三方与图像来源

本项目不包含 ai-pose-gallery-zh 的原始图片、全量数据、第三方生图CLI二进制或模型权重。

内置8张姿势PNG为本次工作台制作的AI生成示意图：最初3张以 ai-pose-gallery-zh 的 upper80v2_P020_front 作为线稿风格参考；其余5张以已生成的双手搭边图作为风格参考。原始参考图库由ギア创建、Anhao中文整理：https://github.com/anhao/ai-pose-gallery-zh 。图库图片的许可不属于MIT，原仓库注明非商业参考用途。当前内置图按非商业动作学习/参考素材提供，不在代码MIT下授予额外商用权利，不声称AI生成就消除了来源限制。

Pillow、NumPy、SciPy、ONNX Runtime、PyMatting通过安装依赖获得，各自适用其项目许可；BiRefNet权重需用户自行取得并遵守其来源许可。源码包不捆绑上述依赖或权重。

用户上传的人物/产品/场景图片属于用户自己的本地数据，不随源码打包。
