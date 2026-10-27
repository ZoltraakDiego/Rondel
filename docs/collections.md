# 统一入口与 28 个研究工作流

当前 28 项职责随 rondel-main 按需发布：Main 七项、Pre 六项、Mid 八项、Post 七项。它们由 Agent 使用实际工具完成，单项职责可以跨阶段接入。路由按当前意图选择，当前任务、来源、状态和实际用户范围在同一 .rondal 档案中接续。

Main 的映射与回传见 [工具图](../skills/rondel-main/references/main-tool-map.md)，具体链路见 [Mid](../skills/rondel-main/references/mid-cycle.md) 和 [Post](../skills/rondel-main/references/post-cycle.md)。论文组织先记录数据与 claim，最后统一取舍，研究收尾交付复现包和资料包。七个本地辅助脚本支持记录与核对，实际科研操作使用当前宿主工具和明确范围。

## main

| 工具 | 职责 | 输入 | 产物 | 状态 |
|---|---|---|---|---|
| [main.open](../skills/rondel-main/references/main-cycle.md) | 接入与恢复 | 项目入口、当前请求 | 当前问题、实际状态与进入位置 | available |
| [main.init](../skills/rondel-main/references/init-dialogue.md) | 渐进式初始化 | 用户表达与指定材料 | 自我介绍、整体理解、推荐计划排期、当前一步与档案位置 | available |
| [main.status](../skills/rondel-main/references/main-cycle.md) | 研究状态 | Init、活动记录、近期用户状态与相关交接 | 当前阶段、客观增量、相关困难与下一步 | available |
| [main.review](../skills/rondel-main/references/drift-check.md) | 主线与方向复盘 | 当前证据、用户理解、计划承诺与阶段条件 | 认识、关键缺口、推进调整与转阶段建议 | available |
| [main.decide](../skills/rondel-main/references/decisions.md) | 人的决定 | 真实用户选择及来源 | 决定笔记与对象状态 | available |
| [main.configure](../skills/rondel-main/references/configuration.md) | 修改约定 | 用户修改与最新文件摘要 | 新版本及影响说明 | available |
| [main.handoff](../skills/rondel-main/references/handoff.md) | 交接与暂停 | 当前问题、决定与实际进度 | 交接及恢复入口 | available |

## pre

| 工具 | 职责 | 输入 | 产物 | 状态 |
|---|---|---|---|---|
| [pre.environment](../skills/rondel-main/references/pre-environment.md) | 资源聚合与环境建立 | 机器、连接、代码与环境入口 | 资源汇总、目标机器、环境卡与实际核验 | available |
| [pre.data](../skills/rondel-main/references/pre-datasets.md) | 找数据集与核验 | 已读论文、正式来源与数据位置 | 数据卡、样本语义、版本和划分依据 | available |
| [pre.protocol](../skills/rondel-main/references/pre-protocol.md) | 数据评价协议与配方 | 数据卡、论文、代码与用户选择 | 共享协议、基线特定配方和修订依据 | available |
| [pre.baseline](../skills/rondel-main/references/pre-baselines.md) | Baseline 选择与版本固定 | 核心阅读、用户理解与协议 | 候选对照、Baseline 冻结设置及复现准备 | available |
| [pre.library](../skills/rondel-main/references/pre-papers.md) | 找论文、精读与实现定位 | 当前问题、已有论文库与正式来源 | 检索日志、领域地图、核心论文卡 | available |
| [pre.framing](../skills/rondel-main/references/pre-framing.md) | 问题与方向引导 | 用户观察、兴趣与材料 | 共同问题、方向比较和候选假设 | available |

## mid

| 工具 | 职责 | 输入 | 产物 | 状态 |
|---|---|---|---|---|
| [mid.issue](../skills/rondel-main/references/mid-issue.md) | 具体问题形成 | 预测现象、条件和影响 | 问题、证据及候选解释 | available |
| [mid.retrieve](../skills/rondel-main/references/mid-retrieve.md) | 相关方法与实现 | 当前问题及成熟来源 | 机制、调用链和迁移比较 | available |
| [mid.design](../skills/rondel-main/references/mid-design.md) | 受控实验设计 | 假设、对照与资源条件 | 预期、否证条件、诊断和清单 | available |
| [mid.implement](../skills/rondel-main/references/mid-implement.md) | 范围内实现 | 当前明确任务或方案、实际源码与来源 | 最小必要改动、对应关系与检查 | available |
| [mid.preflight](../skills/rondel-main/references/mid-preflight.md) | 执行前核对 | 实际代码、配置和环境 | 执行快照、覆盖和真实问题 | available |
| [mid.execute](../skills/rondel-main/references/mid-execute.md) | 有限清单执行 | 批准方案和实际可用资源 | 运行记录、异常和产物引用 | available |
| [mid.inspect](../skills/rondel-main/references/mid-inspect.md) | 结果有效性 | 原始产物和实际协议 | 完整性、口径和有效范围 | available |
| [mid.analyze](../skills/rondel-main/references/mid-analyze.md) | 研究分析 | 有效结果与诊断 | 收益损伤、机制、解释和选择 | available |

## post

| 工具 | 职责 | 输入 | 产物 | 状态 |
|---|---|---|---|---|
| [post.converge](../skills/rondel-main/references/post-converge.md) | 架构与模块收敛 | 匹配候选和研究证据 | 核心架构、作用及保留依据 | available |
| [post.mechanisms](../skills/rondel-main/references/post-mechanisms.md) | 机制沉淀 | 模块、测量与干预 | 功能标签、证据类型和机制关联 | available |
| [post.claims](../skills/rondel-main/references/post-claims.md) | 论点与局限 | 发现、对照和适用条件 | 性能、机制、归因与局限清单 | available |
| [post.visualize](../skills/rondel-main/references/post-visualize.md) | 视觉与图表 | 项目视觉规范及真实数据 | 图表、统计和来源清单 | available |
| [post.write](../skills/rondel-main/references/post-write.md) | 论文表达 | 中心问题、证据和投稿格式 | 故事线、章节、引用与修订 | available |
| [post.submission](../skills/rondel-main/references/post-submission.md) | 投稿准备 | 目标投稿及官方要求 | 日期时区、内部排期和材料清单 | available |
| [post.closeout](../skills/rondel-main/references/post-closeout.md) | 研究收尾与成果交付 | 当前成果、实际版本、有效证据、未完项与用户收尾范围 | 复现包、资料包、验证范围、研究回顾与告别 | available |

可用表示流程、记录和路由已接入。文件与结构测试、实际科研操作、科学判断和对话体验分别记录，证据原文按需要展开。
