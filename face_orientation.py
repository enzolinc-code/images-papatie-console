"""Face direction applies only during character generation, never scene placement."""
FRONT_SUFFIX='人物脸面朝正前方，视线直视观众；枕臂动作保留接触所需侧倾，不变成侧脸。'
def apply(tasks,body,asset_path):
 if body.get('mode') not in ('poses','rebuild'):return
 mode=body.get('face_mode','front')
 if mode not in ('front','original'):raise ValueError('脸部朝向无效')
 identity=body.get('face_reference') if mode=='front' else None
 if identity:asset_path(identity)
 for task in tasks:
  prompt=task['prompt'].replace(FRONT_SUFFIX,'')
  if mode=='front':
   rule='【本次脸部朝向最高优先级】脸的正面朝向镜头，双眼直视镜头，不是只转动眼珠。需要将侧脸转正，合理适配头颈。此项明确覆盖原图和其他锁定要求中的头脸朝向、视线及必要头部角度锁定；保留人物身份、五官特征、肤色、发型、服装和配饰，尽量保持原趴趴姿势、双手位置、手指结构及遮挡关系。托腮/枕臂需保留自然接触，不通过改变手势规避转脸。'
   if identity:
    task['refs']=list(task['refs'])+[identity]
    rule+=' 图'+str(len(task['refs']))+'是同人物的正脸身份辅助，只辅助脸型五官相似度，不提供服装、配饰、发型或动作，不得把它的姿势复制进结果。'
  else:rule='【本次脸部朝向最高优先级】保留图1人物原有头脸朝向和视线，不强行转正，不改变眼神方向。人物制作所选身体/手部姿势仍按动作要求；本选项仅控制头脸朝向。'
  task['prompt']=prompt+'\n'+rule
  task['face_mode']=mode
  task['face_reference']=identity
