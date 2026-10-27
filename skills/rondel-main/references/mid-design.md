# mid.design：设计能够区分解释的有限对照

读取选中的问题与假设、可信 Baseline、成熟来源和冻结设置，说明这轮结果将改变哪项判断。先给一个有区分力的对照，再确定允许改变什么、保持什么，以及哪些结果支持、削弱或仍无法区分解释。容量、训练预算、输入特征、监督、接入位置等替代解释按与当前问题的实际关系检查，避免无边界参数扫描。

还不清楚该检验什么时，可以先做有限观察或诊断，明确希望了解的差异、检查对象、记录和停止条件。此时 hypothesis 字段如实写明探索问题与尚无方向性假设，expected_result 写预期获得的信息，falsification 写什么结果无法支持当前猜想或仍无法区分；不制造预期数字。探索后提出的假设保留形成时间，后续确认性对照沿实际冻结方案进行。

使用 [实验方案](../assets/templates/experiment.md) 创建 experiment 草案，填写 hypothesis、expected_result、falsification、scope 和 setting_refs。预期可以是有依据的行为方向，不编造目标数字；预算与运行时间未知时注明待核对条件。模型训练、冻结编码器的诊断、离线重评和工程验证分别说明，完成标准覆盖指标、预测行为、代价及比较单位。

范围用有限 scope.run_keys 标明每个条件与种子，scope.max_attempts_per_run 默认一次，scope.max_total_attempts 默认清单长度；重试与额外条件必须有对应范围。required_setting_purposes 默认包含 dataset、protocol、baseline、environment，不适用项在具体方案中由真实选择明确。用户采纳后沿 reviewable → approved 保存当时范围，批准正文与设置引用冻结，方案变化创建关联新方案。

研究者本轮最小行动是解释关键对照为什么能区分两种可能，Agent 整理实现、清单与检查点。设计可以独立完成而不启动训练；已经获准的有限方案直接接续。下一步按材料进入 mid.implement 或 mid.preflight，明确科学解释与执行条件仍各缺什么。
