# 记录合同 v1

论文材料取舍使用 discussion、purpose: paper_material_selection，保存当前范围、实际审阅覆盖、关键数据与候选 claim、主文/补充/档案/待核验去向及理由。收尾使用 reproduction_package、materials_package、project_closeout 的 discussion，关联实际交付版本、清单、验证范围与用户选择。导出目录为 `.rondal/deliverables/<release-id>/`，文件核验不改变科学状态或阶段，任何阶段均可沿真实用户选择归档。

项目记录统一保存在用户工作区的 `.rondal/` 中，使用 UTF-8 Markdown 和 YAML 文件头。共用字段为 schema_version、id、project_id、type、display_name、status、revision、refs 和 updated_at。标识在创建后保持稳定，display_name 使用技术或任务语义；正文保留人的文字，更新版本时保存旧文件和状态事件。

上下文路由默认输出字段受控、有字符预算的任务包，原正文按导航展开，普通请求不加载完整索引。context_registry 为独立 discussion，entries 按记录引用保存 active、archive、temporary 和理由，只管理默认可见性，原记录与冻结定义不变。归档目标仍可显式查找，不因归档自动改变方向、假设或结果状态。

阶段文档使用 discussion、purpose: phase_summary，summary_of 与 summary_for 指明来源和服务阶段，brief 保存短小结构化内容，正文保留完整接续信息。source_snapshots 固定来源记录版本和摘要，setting_refs 固定实际设置；真实决定使用 recorded decision 引用。open 草案经 routing.py publish 核对和实际用户审阅后进入 recorded，reviewed_by 保存来源，已审阅文档封存，新认识创建新草案；发布不改变 phase。

引用使用 `record:<id>` 关联项目对象，`project:<relative-path>` 关联项目内文件，也可记录外部路径或正式来源 URL。外部来源需要相应任务核验，文件校验不会据 URL 或路径存在推断科学有效。Init 保存当前有效的 research_anchor、bindings、collaboration、next_step、ready_for、phase 和 activity。

`project:` 的相对基准为 `.rondal/`，记录文件夹、Init、索引和历史均位于该目录，内部状态位于 `.state/`。工作区根目录不用于新建 Rondel 的分类文件夹，已有代码、数据、稿件与产物通过位置绑定关联。Init 正文保存一个完整的用户理解段落和当前计划摘要；完整计划可用带 `purpose: research_plan` 的讨论记录保存，`next_step.plan_ref` 与 `refs` 关联它，用户采纳另有决定来源。

research_anchor 包含用户原话 user_statement、共同问题 problem、开放问题 open_question、方向状态 direction_status 和确认来源 confirmed_by。可增补 priority、current_question 与 scope，由明确用户来源修订。AI 候选解释和旁支保存在讨论、假设或方向记录中，不自动变成共同主线。

Init 收束保存一句可检索的 `research_anchor.search_summary`，并在整体理解段落呈现。configure 将它同步到画像 `research_domain.summary` 与实际 source，反向更新该画像条目时也同步锚点；两处显式提交时必须一致。旧档案可以在正常恢复中补齐这一项，领域摘要与核心问题分别保存。

研究者画像保存在可选的 collaboration.profile 映射中，条目可按实际需要命名为 background、experience、goal、constraints、preferences，每项包含简短的 summary 和真实来源 source。访谈时可进一步使用 addressing、support_needs、interests、explanation、question_rhythm、expression、feedback 等条目，按来源分别保存；旧档案已有命名沿用，避免同义条目冲突。只写入用户表达或认可的内容，未知项省略；待核对的 AI 推断保留在对话草稿。画像用于当前项目的合作，研究问题仍由 research_anchor 保存；guidance 与 execution 保留原有语义。旧档案无需补齐画像即可继续，修订通过 configure 更新 collaboration，沿用人的来源、版本与历史规则；这些可选条目的内容由对话核对，脚本不做语义校验。

用户主动表达且影响当前安排的理解、时间、精力或阻碍，可按需要保存到 collaboration.current_state，附 summary、source、recorded_at 与 task_ref 等来源和范围信息。它是可更新的近期状态，与长期 profile 分开。AI 的观察、推测和停滞分析保存在讨论中，不能借 human 标记制造用户自述；语义判断由 Main 结合实际交流完成。

Main 可使用带 purpose: literature_map、core_paper、main_review 或 phase_review 的 discussion 记录保存领域地图、核心论文、工作复盘与阶段审阅。核心论文分开关联 AI 阅读、用户自述、用户摘要、复现与局限；Main 复盘保存客观增量、相关主观状态、未完成承诺、行动与检查点；阶段审阅列明条件和证据。next_step.review_ref 和项目 refs 可定位最近记录，阶段变化仍沿用实际人的决定；这些用途标签不是新增的脚本状态或自动判定器。

Pre 退出评审在 phase_review 上增加 review_type: pre_exit，保存六项条件、阻碍与有界补齐、带入项、推荐结果和首轮中期任务。已经进行评审与正常退出条件满足分别记录，真实决定通过独立 decision 关联；阶段、当前计划与 next_step 据此接续。带入项保留原状态与负责人、触发条件或检查点，提前转阶段保留缺失条件，转阶段不自动批准运行。

前期数据、环境、协议与机器卡使用 resource，通过 purpose 区分 dataset、environment、protocol、machine，基线选择使用 purpose: baseline_selection 的 discussion。机器使用稳定 host_id，位置保留目标系统的路径字符串；观测时间、来源、单设备可用量和真实占用与静态配置分别记录，资源候选不构成预留。每次实际运行关联机器、数据、环境、协议与产物入口。

正式 Pre 使用 purpose: preparation 的 discussion 总表，保存 focus 与 tasks。领域痛点和核心问题为 purpose: field_pain、core_question 的 question，核心问题的 pain_refs 关联痛点，focus 保存当前集合与 primary_question_ref。任务完成关联证据，版本或依据变化后有效状态需要重新审阅；机器等待、用户当前状态与科学问题判断继续分别记录。

选定数据、协议、Baseline 和环境使用 purpose: dataset、protocol、baseline、environment 的受管理资源，包含 setting_key、setting_version、setting_state 和 spec。checked 草案沿真实用户来源冻结，定义与正文摘要保存到 definition_sha256，旧定义不可覆盖；运行观测仍可单独更新。设置变化由 preparation.py 创建 supersedes 指向旧版的新草案，核验和采纳后冻结；记录 revision 与设置 version 分开。

实验和运行的 setting_refs 使用 ref、version、definition_sha256 固定实际设置，已批准或已准备执行的对象不能事后改绑。历史事件中的 preparation_change 保存时间、原因、来源、变化字段、依赖追踪及 impact_review；潜在影响不自动改变旧结果有效性。Todo 与 Changelog 是可重建投影，来源为总表和事件，定义见安装包内前期跟踪说明。

实验方案批准后保持冻结，run 记录实际执行，purpose: experiment_analysis 的 discussion 汇总有效结果与研究者解释；purpose: manuscript 的 discussion 可承载论文工作稿。中后期职责以按需流程使用这些记录，正式身份、状态与来源由现有接口维护；本地辅助检查不替代真实运行或科学判断。

bindings.notes 指向 .rondal 主档案，用户另行指定的笔记视图位置可保存在 bindings.notes_view，注明 format、location 与来源。视图展示平铺属性并保留核心记录身份和版本，导出清单在 .state/note-views.json；研究者编辑被保留，回收为 purpose: note_feedback 的待审阅 discussion。批注与视图元数据不会直接改写科学状态或批准范围，软件适配不改变核心证据与来源规则。

协作依据 source 包含 kind、reference 和 quote；明确的人类选择使用 user_message 或 user_note。source 用于记录真实交流，平台权限和研究执行仍以当次有效指令为准。自动消息、模型转述和历史资料保留其来源属性。

脚本以排他锁串行写入，以 expected 内容摘要防止覆盖人工修改，单文件通过原子替换保存。提交前写入 pending 意图日志，历史事件记录到 events.jsonl；中断后用显式 recover 完成保存，发现新的人工修改则保留现场供核对。index.md 只更新带 Rondel 标记的生成区，之外的文字保留。

snapshot 保存来源路径、字节数、摘要和 Init 版本，表示来源清单。实际实验还应保存对应配置与源码、环境锁和持久模型状态；大产物由实验目录保管。索引可以显式重建，原始记录是研究事实的核对来源。

中期讨论用途为 research_issue、method_source、implementation_note、preflight、run_inspection、experiment_analysis，后期为 convergence、mechanism、claim_evidence、figure_plan、manuscript、submission_package；正式要求使用 resource、purpose: submission_requirements。next_step 可关联 task_ref、question_ref、hypothesis_ref、experiment_ref、claim_ref、manuscript_ref，路由以具体锚点和关联记录定位，默认不加载整个项目的运行或主张。

新方案的 scope.run_keys、max_attempts_per_run、max_total_attempts 固定有限清单与尝试预算；run 保存 experiment_ref、run_key、attempt 和 setting_refs，失败保留原记录。evidence.py 只读核对批准范围、版本、登记尝试和重试条件，实际就绪、执行与产物有效性各有来源。
