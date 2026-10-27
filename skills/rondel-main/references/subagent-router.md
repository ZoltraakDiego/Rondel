# 轻量 subAgent：主动识别意图，主 Agent 保留控制

先按 [入口检查](entry.md) 运行脚本，缺失档案的明确首次启动先落盘并进入 Init，已有档案再进行这里的分类。Rondel 已启用且需要识别新任务时，主 Agent 主动调用一次轻量路由 subAgent，再校验其结果并加载当前模式的上下文。目标或对象改变、范围修正和需要重新识别的任务变化属于触发点，同任务连续追问、机械步骤或已明确队列项沿已校验结果接续。

## 输入保持小，返回保持固定

先用 routing.py intent 生成 seed：当前动作请求、短小的 project_id/phase/current_mode/task_label、可选的明确目标引用、可用模式和只读约束。禁止将完整对话、项目画像、阶段文档全文、索引或研究证据交给路由 subAgent；长材料只给动作与位置，关键限制继续保留。默认请求最多 2400 字符、提示最多 600 字符、整体 seed 最多 4000 字符，超过时先整理请求而非静默截断。

subAgent 使用 [共享分类提示词](../assets/templates/router-subagent.md)，只返回 mode、intent、read_only、targets、needs_main_review 和 reason。输出默认最多 1200 字符，每个新意图最多一次轻量调用，不进行多模型投票或递归委派。它不读取文件、不使用工具、不写记录、不决定研究方向，也不决定新建 session。

主 Agent 用 validate-intent 校验字段、模式、目标白名单、只读约束与 request_key，再对照当前用户原话核对遗漏或歧义。request_key 用于关联当前输入与子任务；中途有新消息改变目标或范围时，旧票据失效，不能直接套在新请求上。即使 needs_main_review 为 false，结果也不是授权；修改、决定、暂停和执行仍由主 Agent 沿实际来源处理。

## 两种宿主的首选配置

| 宿主 | 首选模型与隔离 | 实际调取 |
|---|---|---|
| Codex | gpt-6-luna、low；不继承父对话 | 当前工具支持时显式指定 model、reasoning_effort、fork_turns: none，或使用生成的自定义 agent 模板 |
| Claude Code | sonnet；非 fork 自定义 subAgent | 调用 rondel-router 自定义 agent，传入 seed；避免用继承完整历史及主模型的 conversation fork |

可调整策略在 [router-models.yaml](shared/router-models.yaml)，生成的宿主模板见 [Codex TOML](../assets/agents/codex/rondel-router.toml) 和 [Claude 定义](../assets/agents/claude/rondel-router.md)。模板从同一提示词和策略构建，主模型不随之改变，实际可用模型与最终配置以宿主为准。模型不可用、没有委派工具、输出失败或存在歧义时，由主 Agent 接手并保留原因；不得伪称完成轻量委派或自动反复升级子模型。

若宿主报告模型 fallback，保留实际型号与原因，不能仍把该次调用描述为首选轻量模型。用户对模型或预算有更严格的明确限制时沿其范围处理。路由票据只在当前任务仍一致时复用，复用的是已经校验的结果，不是把新的研究任务不断追加给同一个带历史的子 Agent。

Codex 自定义 agent 和模型配置依据 [官方说明](https://learn.chatgpt.com/docs/agent-configuration/subagents)，本次宿主已支持显式 Luna 与不继承父对话的调用。Claude 定义与 model: sonnet、omitClaudeMd 依据 [官方说明](https://code.claude.com/docs/en/sub-agents)，当前模板保留 Read 为工具兼容入口，但分类提示词禁止使用任何工具。Claude 的结果接回、等待方式与启动时加载内容依实际版本核对，未取得结果时不能声称路由完成。

## 调用以后再读研究上下文

子 Agent 完成后，主 Agent 先做 [session 边界判断](session-boundaries.md)，再根据校验后的主要模式调用 packet。路由分类使用内部子 Agent，用户可见的新 session 是另一个选择，不能用 create_thread 给每次分类新开用户任务。上下文包的读取与研究操作保持原合同，轻量分类不替代科学判断。

子 Agent 同样产生调用与上下文开销，是否降低总消耗需要实际使用量观察。当前策略通过小输入、短输出、单次调用和连续任务复用控制新增开销；不保证仅换模型就必然减少某种额度。模板与策略随技能发布，安装或启用实际宿主配置按用户选择完成。
