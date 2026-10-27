# 配置与修订

领域检索摘要使用 research_anchor.search_summary，configure 自动同步画像 research_domain 与来源。更新该画像条目也会同步锚点；两处同时提交时必须相同，其他画像条目按原规则保留。新设置绑定使用 baseline，旧 benchmarks 字段在核对前保留历史，不自动改写已有配置。

数据、协议、Baseline 和环境定义采用 [前期设置版本](pre-tracking.md)，已确认版本不通过位置配置或普通正文更新覆盖。定义变更先建立关联草案，记录对原结果的潜在影响；机械观测和检查状态仍可单独更新。绑定调整与设置版本变化的实际含义分别说明。

Init 保存当前共识和位置入口，详细资源与规范保存为关联材料。位置绑定可以包括 notes、papers、code、data、environment、artifacts、protocol、recipe、baseline、visualization 和 submission；每项注明位置、用途、来源与核验状态。机器使用 SSH 别名、目录和环境入口定位，认证材料留在既有认证机制中。

用户指定工作区后，Rondel 档案与更新定位到其中 `.rondal/`，`bindings.notes` 指向实际档案位置。代码、数据和稿件保留原处，已有材料通过绑定关联。整体理解和计划摘要可通过 `configure` 的 `body` 更新，保留正文中的其他有效内容与旧版本。

协作方式包括引导深度与执行粒度。引导可选 guided 或 concise；执行可选 discussion、step、approved_cycle 或 approved_batch，后两者分别对应一个具体方案或有限清单。模式表达用户偏好，实际动作依据当前已确定范围。既有项目配置和用户明确修正优先。

研究者画像按需保存在 collaboration.profile，每项包含 summary 与 source。用户修正经验、目标或偏好时更新相关条目；configure 对 profile 按条目合并，其他有效画像条目保留，更新前仍读取最新内容并使用实际摘要。既有档案没有画像时照常工作，在相关对话中逐步补充。

访谈具体问法、保存对象与复核时机见 [问题清单](init-questions.md)。研究者的成长目标与当前项目的近期优先项分别保存，解释深度、提问节奏与表达偏好可以使用独立画像条目保留各自来源。工作粒度是协作偏好，当前具体执行范围仍由相关任务与用户决定记录。

写入前重读目标文件并计算 expected 摘要，脚本在摘要不一致时要求重新理解当前内容。修改配置保留正文和旧版本，并记录来源、原因和受影响的比较。已经执行的实验继续绑定原配置；拟议研究变化先进入讨论，用户决定后再更新主线。

若用户直接人工编辑笔记，保留其内容；通过显式 reindex 重建索引。只读状态检查发现索引过期时报告需要核对，保持读操作无写入。更多字段见 [note contract](shared/note-contract.md)，请求格式见 [helper](helper.md)。
