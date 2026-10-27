# 本地记录辅助脚本

新请求先按 [路由指引](router.md) 使用 [routing.py](routing-helper.md) 组装本轮上下文，再按需要调用记录接口。原 context 命令保持兼容，只返回定位信息，不要求读完它列出的整个索引或交接。阶段沉淀与归档使用独立上下文记录，正常记录、设置和结果继续遵守下文合同。

脚本位于 `scripts/records.py`，依赖 Python 3.11+ 与 PyYAML。使用项目已有且确认的 Python 环境，仓库开发环境可通过 uv 安装。终端输出英文摘要和文件位置，JSON/JSONL 只写入指定文件。脚本本身不调用模型、网络、SSH 或外部进程。

`--root` 传入用户工作区，记录自动定位到其中 `.rondal/`；直接传入 `.rondal` 路径也可，不会再次嵌套。Python API 的项目操作采用同样规则，可用 `archive_root(workspace)` 获得实际档案目录，读取 `init.md`、计算摘要或定位记录时使用这个目录。`project:` 与记录相对路径均以 `.rondal/` 为基准，内部索引、锁和恢复日志存放于 `.rondal/.state/`。

旧版在工作区根目录生成的档案需要先核对并迁入 `.rondal`，内部 `.rondel` 状态目录相应调整为 `.state`，再验证与重建索引。发现旧档案时脚本报告需要迁移，保持现有内容供核对；迁移只处理确认属于 Rondel 的记录，业务文件和外部材料留在原处。

## 命令

```text
uv run python <skill>/scripts/records.py --root <notes> init --name <name> --statement <user-words> --source <source.yaml>
uv run python <skill>/scripts/records.py --root <notes> configure --request <patch.yaml>
uv run python <skill>/scripts/records.py --root <notes> record --request <record.yaml>
uv run python <skill>/scripts/records.py --root <notes> update --request <update.yaml>
uv run python <skill>/scripts/records.py --root <notes> decide --request <decision.yaml>
uv run python <skill>/scripts/records.py --root <notes> transition --request <transition.yaml>
uv run python <skill>/scripts/records.py --root <notes> context --mode review --target <record-id>
uv run python <skill>/scripts/records.py --root <notes> validate
uv run python <skill>/scripts/records.py --root <notes> reindex
uv run python <skill>/scripts/records.py --root <notes> recover
uv run python <skill>/scripts/records.py --root <notes> snapshot --destination <new.yaml> --source <source-file>
```

## 请求字段

`configure` 使用 patch、expected、actor、reason、可选 source 和 body；expected 是重读目标文件后计算的 SHA256。body 用于保存已整理的用户理解段落、推荐计划与当前起点，省略时保留原正文，旧版照常归档。patch 中的 bindings 按键合并，主线、阶段、协作和 ready 状态变更需要明确的人的来源。`record` 使用 kind、name、body、refs 和可选 fields，默认创建候选或初始状态。

画像通过 `configure` 的 `patch.collaboration.profile` 保存，使用 `actor: human` 并提供当前用户来源。profile 是可选映射，每项包含 summary 和 source；例如 experience.summary 可记录“能复现代码，希望重点讨论结果分析”，其 source 引用用户实际表达。更新前保留整个 profile 中仍有效的条目，省略的未知维度无需补齐；脚本负责版本化保存，内容由当前对话整理。

完整计划可用 `record` 创建 `kind: discussion`，通过 `fields: {purpose: research_plan}` 标识用途。用户认可或修订计划后用 `decide` 保留实际选择，项目的 `next_step.plan_ref` 关联 `record:<计划id>`，相关计划与决定引用同时加入 `refs`。`context --mode open --target <计划id>` 可定位当前计划，普通状态查询仍只读摘要与相关记录。

领域地图、核心论文、Main 复盘与阶段审阅也使用 discussion，purpose 分别为 literature_map、core_paper、main_review、phase_review。最近复盘可通过 next_step.review_ref 和 refs 关联；context 使用对应 target 定位。collaboration.current_state 保存有实际用户来源的近期状态，AI 推测留在讨论记录，脚本不会自动验证理解程度、累计停滞次数或判定阶段条件。

`decide` 使用 name、body、source 和 refs，只保存人的决定。`transition` 使用 relative、state、expected、actor、reason 和可选 source，校验对象状态边；实验批准前要求 hypothesis、expected_result、falsification 与 scope。需要人的转换必须使用 actor: human 和真实来源，AI 不自行制造原话。

`update` 使用 relative、patch、expected、actor、reason、可选 source 和 body，补充来源或分析内容；省略 body 时保留原正文。状态通过 transition 改变，批准后的假设与 scope 保持冻结，新的研究方案建立关联的新记录。来源、身份及批准信息不通过通用 patch 重写。

```yaml
kind: user_message
reference: "本项目当前对话中用户的具体回复位置"
quote: "用户实际表达的选择"
```

context 默认只读并打印需要读取的位置；`--out` 会在指定研究目录内保存结构化定位清单，需要当前写入范围允许。脚本只提供定位和结构核验，语义分析仍由研究者与 AI 完成。索引过期时先核对新记录，再显式 reindex。

context 也支持 pre.framing、pre.library、pre.data、pre.protocol、pre.baseline 和 pre.environment，按需返回相应前期流程与指定记录。资源汇总与候选筛选见 [资源辅助脚本](resource-helper.md)，Markdown/Obsidian 视图与批注回收见 [笔记适配](note-adapters.md)。所有辅助脚本都可在完整安装包内独立使用。

当前全部 28 个研究模式均可定位，Mid 与 Post 的具体入口分别见 [中期工具链](mid-cycle.md) 与 [后期工具链](post-cycle.md)。routing.py 按具体任务引用约束上下文，records.py 负责记录、版本与状态，有限清单与尝试预算用 [evidence.py](evidence-helper.md) 只读核对。实际运行、科学分析、图表生成与投稿使用当次可用工具，记录状态按真实产物和来源更新。

研究收尾使用 [closeout.py](closeout-helper.md) 按显式清单新建两份包并核对文件摘要。导出不执行科研命令、不自动归档项目，文件完整性和结果复现程度分别保存。任何阶段均可沿实际用户选择进入 archived，未完成问题与原始记录继续保留。

前期初始化、设置冻结、Todo 与 Changelog 使用 [preparation.py](preparation-helper.md)。已有总表会进入 open、status、review、handoff 与 pre 上下文，context 保持只读；旧名 pre.benchmarks 仅兼容映射到 pre.baseline。领域摘要通过 configure 保存 research_anchor.search_summary，并同步画像 research_domain，见 [Init 收束](init-synthesis.md)。
