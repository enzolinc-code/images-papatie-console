"""User-authored consistency requirements; prompts, not an automatic output verifier."""
from pathlib import Path
RULES=(Path(__file__).parent/'prompts/lock-requirements.txt').read_text('utf-8').strip()
MODES={'rebuild','scenes','poses','correct_hands','correct_identity','correct_material'}
def context(mode):
 if mode=='rebuild':return '参考分工：图1同时是人物身份、原动作、可见手指、遮挡与光影的唯一依据；不使用姿势库，不改变原动作，不虚构屏幕。只分离背景并高清重构。'
 if mode=='poses':return '参考分工：人物身份、服装、发型以原人物照片为准；姿势锁定指本次所选目标趴趴动作，不照搬原站姿。手指依照目标动作和可见遮挡关系自然重构，不强行补全。透明图稿不额外画屏幕。'
 if mode=='scenes':return '参考分工：原人物透明母版（图2）是身份、姿势、手指和服饰的依据；场景图（图1）只提供机位、屏幕承托边、环境光向与色温，不参考其中旧人物身份或动作。若有身份母版则只辅助面貌。人物动作与场景机位只允许整片合理适配；保留亚克力薄边与实物反射，禁止额外油亮皮肤。'
 return '参考分工：图1为当前成品，人物姿势、可见手指及遮挡以图2原动作母版为准；身份母版如有则辅助面貌。锁定图1场景机位、环境光影与亚克力实物质感。仅修正本次所选问题，不锁住图1已有错误，不改变其余正确特征。'
def apply(mode,prompt):
 if mode not in MODES:return prompt
 return prompt if '【人物锁定】' in prompt and '【检查要求】' in prompt else prompt+'\n'+context(mode)+'\n'+RULES
