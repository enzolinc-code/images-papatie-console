/* User consistency requirements are added quietly to newly submitted requests. */
(()=>{
const rules="【人物锁定】\n保持同一人物的脸型、五官位置、眼睛形状与颜色、表情、肤色、发型、发色、发际线及身体比例一致。保留原有服装、配饰、颜色和纹理，不擅自增减细节。\n\n【姿势锁定】\n精准保留参考图中的趴伏姿势、头部倾斜角度、肩膀高度、手臂弯曲角度、手腕朝向及身体重心。保持人物与屏幕上沿的接触关系，双手搭放位置、下巴位置及遮挡顺序一致，不改变镜头视角和透视。\n\n【手指锁定】\n逐一对应参考图中可见手指的数量、位置、弯曲程度、指尖朝向及相互遮挡关系。被遮挡的手指保持遮挡，不强行补全。手部结构自然，不出现多指、少指、粘连、断指、关节错位或手掌变形。\n\n【光影与质感锁定】\n保持参考图的光源方向、柔和程度、色温、明暗分布、高光位置及阴影深浅一致。保持相同的皮肤、头发和衣物质感，表面干净细腻，不额外添加油亮反光，不过度磨皮。\n\n【检查要求】\n输出前检查人物身份、姿势、手指结构、光影及外轮廓；出现偏差时优先修正，不能用改变姿势或隐藏手部的方式规避问题。";
const context={"scenes": "人物/姿势/可见手指以图2原人物母版为准；图1只提供场景机位、屏幕承托边、环境光向和色温，不参考旧人物身份或动作。保留亚克力材质反射，不额外添加油亮皮肤。", "poses": "人物服装发型以原照片为准；姿势锁定指本次所选目标趴趴动作，不照搬站姿。手指按目标动作与可见遮挡自然重构；透明图稿不画屏幕。", "correct_hands": "图1为当前成品，图2原人物母版提供身份、姿势和手指，额外身份图仅辅助面貌；保持图1环境光影、机位与亚克力材质。只修正本次问题，不锁住成品已有错误，也不改变其他正确特征。", "correct_identity": "图1为当前成品，图2原人物母版提供身份、姿势和手指，额外身份图仅辅助面貌；保持图1环境光影、机位与亚克力材质。只修正本次问题，不锁住成品已有错误，也不改变其他正确特征。", "correct_material": "图1为当前成品，图2原人物母版提供身份、姿势和手指，额外身份图仅辅助面貌；保持图1环境光影、机位与亚克力材质。只修正本次问题，不锁住成品已有错误，也不改变其他正确特征。"};
const originalApi=api;
api=async function(path,body){
 if(body&&['/api/plan','/api/jobs'].includes(path)&&Object.hasOwn(context,body.mode)){
  const extra=String(body.extra||'');
  if(!extra.includes('【人物锁定】')||!extra.includes('【检查要求】')){
   const combined=extra+'\n'+context[body.mode]+'\n'+rules;
   if(combined.length>(state.health?.consistencyRules?6000:3000))throw Error('补充要求过长，请缩短后再提交；默认人物/姿势/手指锁定会自动加入');
   body.extra=combined;
  }
 }
 return originalApi(path,body);
};
})();
