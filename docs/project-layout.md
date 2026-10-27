# 技能仓库与研究档案目录

技能仓库保存共享流程、模板、辅助脚本、文档和匿名案例。当前 skills/rondel-main 同时承载 Main、Pre、Mid 与 Post 的 28 个工作流，其他独立入口仍是后续拆包选择。共享源同步到安装包，单独复制完整技能目录即可保留引用与辅助脚本。

```text
rondel/
├── README.md / README.en.md / LICENSE
├── pyproject.toml / uv.lock
├── skills/
│   ├── rondel-main/                 当前可用
│   │   ├── SKILL.md
│   │   ├── agents/openai.yaml
│   │   ├── references/              按任务读取
│   │   ├── assets/templates/
│   │   └── scripts/                routing.py、records.py、preparation.py、resources.py、note_views.py、evidence.py、closeout.py
│   ├── rondel-prep/                 后续能力
│   ├── rondel-lab/                  后续能力
│   └── rondel-paper/                后续能力
├── shared/
│   ├── contracts/ / context/ / styles/ / templates/
│   └── tool-catalog.yaml
├── adapters/                       Codex 与 Claude Code
├── scripts/                        记录入口与打包
├── docs/                           目标、工具、状态与扩展
├── examples/                       从 Init 到 claim 的匿名案例
└── tests/                          文件不变量与对话验收用例
```

用户在 Init 时指定工作区，Rondel 的记录与更新全部位于其中的 `.rondel/`。下面展示档案的目标结构，各部分按任务首次需要创建，初次接入不预建空的分类目录。已有代码、数据和产物保留原有位置，后续工具使用相关位置绑定。

```text
<用户指定工作区>/
├── 原有研究文件与目录              代码、数据、稿件等按原结构保留
└── .rondel/
    ├── init.md                     整体理解、研究起点与计划摘要
    ├── index.md                    活动对象与人工补充
    ├── discussions/                完整计划与其他讨论
    ├── decisions/ / handoffs/       用户决定与交接
    ├── setup/                      环境、数据、协议等记录
    │   └── preparation-todo.md      显式重建的前期待办投影
    ├── knowledge/                  论文卡片与成熟方法入口
    ├── research/                   问题、方向与假设
    ├── experiments/                方案、运行与分析记录
    ├── claims/ / paper/            论点、写作与投稿记录
    ├── sources/                    原始材料的版本摘要
    ├── deliverables/               显式生成的复现包、资料包与文件清单
    ├── history/                    旧版本与变化历史
    │   └── preparation-changelog.md 显式重建的设置变更与结果影响投影
    └── .state/                     可重建索引、锁与恢复日志
```

辅助脚本接收工作区或它的 `.rondel` 路径，后者不会重复嵌套；`project:` 引用以档案目录为基准。已有代码、数据、权重、PDF 和远程产物通过路径、URL、版本与摘要关联，新的研究执行产物按明确方案和位置保存。旧版根目录档案先核对归属与修改，再迁入 `.rondel/`，内部 `.rondel` 状态目录改为 `.state`，保留项目标识、记录与历史。

远程实验通过机器、数据和环境资源卡绑定 host_id 与目标路径，主档案只保留来源、版本与运行入口。用户需要在已有笔记库中阅读和批注时，另行指定一个可见视图目录，导出登记在 `.state/note-views.json`。真实库和大型产物不会因初始化自动迁移，研究者对视图的改动先回收为待审阅反馈。

阶段文档和上下文归档导航都是 discussions 下的正常记录，purpose 分别为 phase_summary 和 context_registry，保留历史与身份。归档只调整索引和默认加载，原文件与冻结定义保持不变；可选上下文包输出放在 `.state/context/`。不需要新增另一套 Robel/Rondel 根目录，实际档案继续使用 `.rondel/`。
