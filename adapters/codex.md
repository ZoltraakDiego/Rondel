# Codex

进入项目首先按 [entry](../skills/rondel-main/references/entry.md) 实际运行 routing.py enter，检查明确工作区的 .rondel；缺失且已明确启动与允许保存时先创建 listening 档案，已有档案再使用脚本短 seed 分类。脚本需有效 Python 3.11+ 解释器，安装包已内置 PyYAML；遇到系统占位解释器或执行错误时先处理，不以口头初始化代替落盘。

路由采用 [主动轻量 subAgent](../skills/rondel-main/references/subagent-router.md)：支持本会话的工具可显式选择 gpt-6-luna、low、fork_turns: none，发送短 seed 并等待结构化分类。可选 [自定义 agent 模板](../skills/rondel-main/assets/agents/codex/rondel-router.toml) 按宿主说明安装到用户选定的 agents 位置；这与 agents/openai.yaml 的技能界面元数据不同。当前没有修改全局模型配置，实际可用型号与配置优先级按 [官方说明](https://learn.chatgpt.com/docs/agent-configuration/subagents) 核对。

用户任务边界变化时按 [session 建议流程](../skills/rondel-main/references/session-boundaries.md) 先整理交接再提出建议。只有明确的新会话请求才使用当前 app 的创建能力，内部路由不使用 create_thread 冒充 subAgent。新任务默认由精简交接包启动，保留当前聊天为历史。

宿主发现与路由可使用 [一句话引导模板](../shared/templates/router-bootstrap.md)，由用户放入选定的 AGENTS.md 或实际宿主配置。Codex 的项目说明发现方式见 [官方说明](https://learn.chatgpt.com/docs/agent-configuration/agents-md)，技能再按需展开相关流程。未安装时沿用户已知源码路径读取入口，不以全盘扫描代替定位。

当前默认使用 [模式识别与上下文路由](../skills/rondel-main/references/router.md)，通过 routing.py discover、packet、lookup 发现档案、加载本轮信息和查询历史。引导句与数据包作为可接入资源提供，本仓库没有修改用户级或系统级提示词、安装 hook 或创建后台拦截器。宿主会话的历史裁剪与压缩独立管理，阶段文档用于恢复。

把发布包中的 `rondel-main` 完整目录复制到目标项目的 `.agents/skills/rondel-main`，保留 references、assets、scripts 与 agents。用户级安装位置以当前 Codex 官方说明和本机配置为准，安装后通过技能列表确认发现。启动示例：`$rondel-main 帮我接入这个研究项目，先理解问题和已有材料。`

技能通过当前可用的文件与检索工具工作，工作区由 Init 确定，档案统一存放在其中 `.rondel/`。记录辅助脚本使用选定的 Python 环境；项目路径只保存在用户档案中。读取已有研究时遵守当前目录说明和当次要求，恢复时从当前计划与任务接续，核对有效范围与实际状态。

尚未安装时可以明确要求 Agent 读取仓库中的 `skills/rondel-main/SKILL.md` 并按其流程工作。源码路径调用、安装后调用、模式选择与档案读取顺序见 [完整调取案例](../examples/usage-cases.md#case-00)；内部模式名表示职责，辅助脚本的 context 负责定位资料。

官方说明：[Build skills](https://learn.chatgpt.com/docs/build-skills)。当前发布包以 rondel-main 为统一入口，包含 Main、Pre、Mid、Post 共 28 项流程与配套模板，研究收尾可交付复现包和资料包。
