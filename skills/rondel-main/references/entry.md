# 第一脚本：档案检查、最小落盘与路由种子

明确进入一个科研项目后，先在用户最新指定的工作区运行 enter，位置优先于宿主旧 cwd 和历史笔记绑定。没有新的位置说明时接续当前任务的明确工作区，不能扫描整盘猜测归属。普通独立问答、技能设计和未启用的项目不执行初始化。

```text
<已验证的 Python> <skill>/scripts/routing.py enter --root <workspace> --request <entry.json>
```

entry.json 包含 request（本轮简短动作）、initialize_missing（是否允许创建缺失档案）、read_only（是否只读）、runtime（codex 或 claude）和可选 source。实际首次启动与已有的保存选择可以使用 initialize_missing: true；source 沿当前消息或仍适用的实际用户来源提供 kind、reference、quote，不能填造用户原话。只读时不能同时要求初始化，尚未确定保存位置时先保持讨论稿。

| 返回 next_action | 主 Agent 接下来完成什么 |
|---|---|
| init，initialized: true | 已创建并核验最小 listening 档案，沿 Init 开场了解用户，重要回答及时回写 |
| init，initialized: false | 尚未落盘；沿当前只读约束或缺失的位置、来源确定下一步，不宣称保存成功 |
| route | 先将返回的 intent_seed 交给一次轻量分类，再校验结果、生成对应模式 packet |
| repair_legacy_archive | 发现旧 `.rondal/`，当前只读或缺迁移来源，保留原目录并明确需要的处理 |
| resolve_archive_conflict | 两套档案或目录归属冲突，展示路径与项目身份，保留两边，不自动合并或覆盖 |

返回结构按实际文件生成，persistence_verified 表示 init.md 已读取并核对；新档案还运行记录验证。新项目只创建最小档案、索引和历史状态，不预建全部论文与实验目录，也不提前标成 ready。真实画像、领域摘要、问题和计划随对话分别保存，用户指定新工作区后重新运行入口，不继续把旧位置当作当前项目。

已有档案时只读取 Init 元数据中的项目身份、阶段和当前任务，不把画像、正文、全部索引或阶段文档交给 Luna。intent_seed 保持原字段和体量约束，主 Agent 仍对照当前原话校验，之后才沿 packet 展开与本轮职责相关的材料。分类不批准执行、推进阶段或新建 session。

## 解释器与依赖

优先使用宿主提供的 Python 运行时或当前项目已验证的解释器。Windows 的 python/py 命令可能指向 WindowsApps 占位入口，启动失败时核对实际路径并切换，不把 PowerShell 最后一条命令成功当成前面 Python 已成功。安装包的 scripts/yaml 保留 PyYAML 6.0.3 的纯 Python 实现和许可证，直接运行辅助脚本无需另行安装系统 PyYAML，也不修改 PATH 或全局依赖。

只有脚本成功返回并实际读取目标档案后，才可说“已经保存”或“已经恢复”。失败时报告具体缺口、完成范围和下一项处理，不把降级的对话草稿称作持久化。现有上下文与档案不相符时回到入口定位，原材料保持不变。

## 兼容旧目录

规范目录是 `.rondel/`，旧 `.rondal/` 只用于兼容识别。入口在原档案身份有效、没有活动写入或未恢复事务、目标不存在且有实际用户来源时原地更名，记录内容、相对引用、版本与历史保持不变。迁移只处理明确工作区内的这套档案，不改现有论文、数据、代码或笔记视图；目录冲突和损坏元数据先定位，禁止删除一边来伪造成功。
