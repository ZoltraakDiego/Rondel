# 路由辅助脚本

项目接入首先调用 [entry](entry.md)：`<Python> <skill>/scripts/routing.py enter --root <workspace> --request <entry.json>`。它先检查真实目录与落盘，新建最小 Init 或返回已有项目的短 seed；后面的 discover、intent 与 packet 保留为相应低层接口。


`scripts/routing.py` 接收 Agent 已经识别的主要模式，输出有预算的上下文数据与来源导航。它不自行调用模型或执行研究，语义识别由 [路由指引](router.md) 完成。原 context 命令继续兼容定位文件，新路由默认使用 packet，避免先展开完整 Init 正文和活动索引。

轻量委派前使用 intent 生成受限 seed，主 Agent 调用实际宿主的 subAgent 后用 validate-intent 校验返回。两条命令不自行调用模型，不读取研究正文，也不写项目状态；实际调用方式见 [subAgent 协议](subagent-router.md)。会话切换由 Main 按 [session 规则](session-boundaries.md) 单独判断。

```text
python <skill>/scripts/routing.py intent --request <current-intent.yaml>
python <skill>/scripts/routing.py validate-intent --seed <seed.json> --result <subagent-result.json> --current-request-key <active-key>
```

intent 请求字段为 request、runtime（codex/claude）、可选 context_hint、allowed_targets 与 read_only_constraint。context_hint 只接受 project_id、phase、current_mode、task_label，目标最多八个 record 引用；request_key 关联当前输入，发生目标或范围变化时重新识别。返回六项路由字段之外的命令、虚构目标、只读范围冲突或过大的结果会被拒绝，执行与 session 创建始终没有因分类而获得授权。

```text
python <skill>/scripts/routing.py discover --start <cwd> --boundary <known-project-root>
python <skill>/scripts/routing.py packet --root <workspace> --mode pre.protocol --stdout
python <skill>/scripts/routing.py packet --root <workspace> --mode main.review --target <record-id> --out .state/context/review.json
python <skill>/scripts/routing.py lookup --root <workspace> --query <terms>
python <skill>/scripts/routing.py lookup --root <workspace> --query <old-direction> --include-archive
python <skill>/scripts/routing.py visibility --root <workspace> --request <visibility.yaml>
python <skill>/scripts/routing.py summary --root <workspace> --request <summary.yaml>
python <skill>/scripts/routing.py publish --root <workspace> --request <publish.yaml>
```

discover 不递归搜索，默认边界为最近 Git 根，没有 Git 时仅当前目录；多个档案返回 ambiguous。packet 接受 Main、Pre、Mid、Post 共二十八个研究模式，general 不读取项目，未建档的专项任务也不会自动写 Init。模式与阶段分开，未登记模式不能作为实际模式调用。

packet 默认上限 6000 字符，可选 1200—20000，显式目标最多八个，相关用途卡默认至多四个。内容为项目锚点、适用偏好、当前任务、阶段 brief、记录卡和导航，原正文不默认内联；过大字段整体转成来源入口。`--stdout` 显式输出紧凑 JSON 供只读上下文组装，未指定时只打印模式摘要；`--out` 仅写 `.state/context/` 内 JSON，不覆盖主记录。

visibility 请求包含 refs、state 和 reason，可选真实 source。state 为 active、archive 或 temporary，refs 为当前项目记录引用；变化保存为正常的上下文登记记录并更新活动索引，原记录不变。归档与科学状态分开，涉及实际研究选择时仍使用正常的决定与状态流程。

summary 请求包含 name、summary_of、summary_for、brief、source_refs、body 与可选 setting_refs。brief 使用 question、findings、decisions、open_questions、carryovers、next_step，下一步至少包含 label；findings 每项必须有 statement、conditions、evidence_refs 与 status。carryovers 包含 task、owner、trigger，decisions 只引用实际 recorded decision，不能把 AI 概括作为人的选择。

```yaml
name: 前期阶段沉淀
summary_of: prepare
summary_for: investigate
brief:
  question: 实际当前核心问题
  findings:
    - statement: 实际观察或仍待验证的解释
      conditions: 适用的数据、协议与比较条件
      evidence_refs: ['record:<actual-source-id>']
      status: observation
  decisions: []
  open_questions: [下一轮仍需区分的问题]
  carryovers:
    - task: 实际带入任务
      owner: 实际负责人
      trigger: 实际复盘点
  next_step:
    label: 已选择或待审阅的首项任务
source_refs: ['record:<actual-source-id>']
body: |
  完整阶段文档，使用对应模板，事实关联实际来源。
setting_refs: []
```

发布请求使用 relative、expected、source；expected 对应重读摘要草稿后的实际字节摘要，source 保留用户实际审阅或采纳的来源。来源变化时先修订草案和快照，已发布文档封存，新认识创建新草案。发布不改变项目 phase，也不创建运行；完整流程见 [阶段上下文](phase-context.md)。

中后期使用 next_step 的具体任务引用或显式 targets 选择上下文。中后期的自动用途卡和类型卡只在有任务锚点时展开，沿方案到运行、运行到分析的有限关系定位，不因共享数据设置串联无关分支；没有锚点时提示选定任务或查询。默认四张相关卡只负责导航，完整比较仍读取清单中的必要证据。
