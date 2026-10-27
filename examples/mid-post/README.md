# Mid 与 Post 的连续使用案例

本例是虚构的少样本时序动作分割项目，用于说明十四项职责如何接续，不包含实际训练结果。假定 Pre 已完成约定阅读与复现，数据、协议、Baseline 和环境均有冻结记录，阶段文档定位到当前问题。Agent 按当前请求选择工具，先形成具体产物再与研究者复盘，每轮只带入相关方案、运行、分析或稿件。

## 从现象到有限实验

**研究者：**“动作类别大致能认出来，但是短动作经常被吞掉。我不确定是视觉语义没分开，还是时序骨干过度平滑。”

Rondel 进入 mid.issue，先定位具体视频、预测与协议，确认“短动作被吞掉”发生在哪些条件，区分观察与两种解释。它保存 question 和 research_issue，并把两种解释保留为候选假设；研究者补充哪些行为最值得追问。随后进入 mid.retrieve，核对成熟方法的正式论文、真实代码版本和调用链，比较视觉特征、融合与时序预测的处理位置。

**Rondel：**“当前需要分清视觉表征与时序处理各自带来的影响。先保持骨干、数据和训练配方一致，比较原条件与一项轻量适配；如果短动作仍无法区分，再针对已观察到的混淆定位特征行为。你可以先解释一下，什么结果会让你更相信视觉语义这条解释，我们据此把预期和否证条件写清楚。”

mid.design 将共同讨论写成 experiment，明确比较对象、主要观察、否证条件和冻结 setting_refs。假设本轮只选择 baseline-s42 与 adapter-s42，各一次尝试，便将它们写入 scope.run_keys，并保存实际用户选择。mid.implement 根据真实来源完成范围内修改，记录源码对应、接口差异和必要检查；工程检查结果只说明这份改动实际检查过什么。

## 从执行到有效证据

**研究者：**“就按刚才两个条件做，服务器用已经登记的那台。”

mid.preflight 读取当前批准版本，用 evidence.py 核对有限清单、尝试预算和设置引用，再由实际工具检查机器、代码、配置、数据与评价入口。若 baseline-s42 已经在跑，mid.execute 接续其真实任务标识，只提交尚未开始且条件就绪的 adapter-s42。每次尝试保存独立 run，任务完成后由 mid.inspect 核验预测、日志、覆盖、选点和协议，检查依据关联到 run_inspection。

如果一次运行产生了不完整预测，Rondel 保留这次尝试并明确无效范围，不把它当成方法失败。默认一次尝试的范围不包含额外重跑，先完成诊断与具体调整，再沿研究者已选择的范围执行。只有检查有效的证据进入 mid.analyze，比较收益、损伤、行为和替代解释，并说明哪些判断仍未解决。

**Rondel：**“先看这轮有效比较是否改变了我们对短动作问题的理解，再决定补哪一项。请你用自己的话说明目前最支持哪种解释；我会把实际观察、你的理解和仍可竞争的解释并列保存。若下一项对照不能改变中心判断，就先收束这条探索。”

## 从研究发现到论文材料

Main 在 [Mid 到 Post 评审](../../skills/rondel-main/references/mid-exit.md) 中核对主问题与候选发现、有效比较、归因、当前版本、研究者理解及有限剩余清单，区分阻碍、带入项和暂存方向。用户选择后先进入 converge，由 post.converge 形成当前方法或发现的收敛版本及保留理由；post.mechanisms 整理模块功能和证据，post.claims 将每条候选主张映射到实际条件与来源。尚未建立机制证据的现象继续按观察表述，正式采用的中心句关联用户真实选择，进入 write 的条件另行审阅。

**研究者：**“我们先按这个中心发现写起来，额外实验只补影响它的内容。”

post.visualize 先明确每幅图帮助核对哪条认识，保存源数据、处理、统计口径与可编辑产物；post.write 据此组织问题、局限、方法、证据和贡献。数字、引用与主张逐项回到来源核对，用户的修改保留版本与理由。若关键比较不足，生成一个有返回条件的有限补充任务，由相应 Mid 工具完成后回到当前稿件。

post.submission 核对用户当前选择的目标、年份和文章类型，从正式要求保存截止日期及时区，再形成具体可审阅材料包。准备完成、上传、正式提交和回执分别记录，执行沿已经明确的目标与材料范围。阶段文档保存当前认识、证据入口、未解项与下一步；重大任务转换时，Main 准备交接后建议是否另开 session。

## 本例中的路由与持久化

| 当前请求 | 路由 | 保存与接续 |
|---|---|---|
| 观察怎样形成问题 | mid.issue | question、hypothesis、research_issue |
| 找能解释问题的成熟来源 | mid.retrieve | method_source 与真实源码入口 |
| 设计有限可归因比较 | mid.design | experiment、scope、setting_refs |
| 落实当前修改 | mid.implement | implementation_note 与实际改动 |
| 核对实际将运行什么 | mid.preflight | preflight、来源快照与结构报告 |
| 执行已确定清单 | mid.execute | run、任务标识、状态与产物入口 |
| 检查产物是否有效 | mid.inspect | run_inspection 与 check_status |
| 解释有效结果 | mid.analyze | experiment_analysis 与假设评估 |
| 固定当前发现与方法 | post.converge | convergence 与有限补充 |
| 整理机制及证据类型 | post.mechanisms | mechanism 与尚未解释之处 |
| 组织主张与边界 | post.claims | claim、claim_evidence 与采用决定 |
| 形成有来源的图表 | post.visualize | figure_plan、统计与实际产物 |
| 组织与修订论文 | post.write | manuscript、相关主张与版本 |
| 核对目标与投稿准备 | post.submission | submission_requirements、submission_package 与真实动作 |

记录统一保存于用户工作区 `.rondel/`，远程数据、权重和日志保持其实际位置，笔记视图按原适配规则导出。显式指定新方案时，本轮上下文优先使用它，不带入上次任务的运行；共享数据设置只作为必要来源。完整流程见 [Mid 工具链](../../skills/rondel-main/references/mid-cycle.md) 与 [Post 工具链](../../skills/rondel-main/references/post-cycle.md)。
