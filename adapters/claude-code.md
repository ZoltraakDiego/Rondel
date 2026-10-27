# Claude Code

路由采用 [Sonnet 自定义 subAgent 模板](../skills/rondel-main/assets/agents/claude/rondel-router.md)，安装位置按 [官方 subAgent 说明](https://code.claude.com/docs/en/sub-agents) 核对。主 Agent 主动调用 rondel-router，传短 seed 并接回分类，选择非 conversation-fork 形式；模板使用 model: sonnet、omitClaudeMd: true 和单轮限制，不切换主模型。模板只允许 Read 作为工具兼容入口，分类提示词禁止使用工具，实际能力与等待方式仍依客户端配置核对。

需要新 session 时先按 [边界与交接规则](../skills/rondel-main/references/session-boundaries.md) 给出建议，明确选择后通过当前客户端完成。不能把提出建议、编写规则或 subAgent 分类当成清空会话的要求，也不复制旧对话全文到新会话。当前没有运行 Claude 的真实委派或修改其用户配置。

宿主引导可采用 [一句话模板](../shared/templates/router-bootstrap.md)，放入用户选定的项目说明；具体宿主发现方式按实际配置核对。技能内部沿 [模式识别与上下文路由](../skills/rondel-main/references/router.md) 工作，按用户意图选择模式，再读取结构化任务包与必要证据。模板不修改全局配置，宿主会话历史仍由宿主管理。

把发布包中的 `rondel-main` 完整目录复制到项目的 `.claude/skills/rondel-main`，保留全部资源。用户级安装可放入当前 Claude Code 支持的用户技能目录，并检查技能发现情况。启动示例：`/rondel-main 帮我恢复研究主线，先读已有 Init 和相关交接。`

核心使用标准 SKILL.md 与普通文件，agents/openai.yaml 是 Codex 的可选界面元数据。Claude Code 使用自己的文件、提问和检索能力完成同样的协作流程。外部资料、聊天摘要和自动跟进内容保留来源属性，当前用户决定与工作范围单独记录。

用户指定工作区后，Init、计划、决定、交接与内部状态统一保存到 `.rondal/`，恢复从当前理解与计划接续。已有研究文件留在原处，通过位置绑定关联。

官方说明：[Extend Claude with skills](https://code.claude.com/docs/en/skills)。当前发布包以 rondel-main 为统一入口，包含 Main、Pre、Mid、Post 共 28 项流程与配套模板，研究收尾可交付复现包和资料包。本适配未安装 hooks、后台任务或自动执行器。
