# 笔记适配：Markdown 与 Obsidian

研究对象和证据关系保持统一，笔记软件只改变展示与交互层。当前主档案仍在工作区 `.rondal/`，通过用户指定的可见笔记目录导出阅读与批注视图；默认不改知识库设置、不安装插件、不迁移原始附件。其他 Markdown 软件使用相同模板与标准链接，Obsidian 视图增加平铺属性、aliases、tags 与已导出记录的双链。

## Obsidian 的文件约定

按 [官方属性说明](https://obsidian.md/help/properties)，属性面板不直接支持嵌套属性，源模式仍可查看嵌套 YAML。主档案保留完整结构化元数据，视图仅展示平铺的记录身份、类型、版本与状态，以及 aliases 和 tags，避免要求研究者在属性面板编辑内部协议。正文保留标准 Markdown，公式使用 `$$` 独立数学块。

按 [官方 Sync 说明](https://obsidian.md/help/sync/settings)，点号文件夹不参与常规 Sync，`.obsidian` 配置目录例外。因此不能承诺 `.rondal/` 自动成为现有库中可见、可同步的研究笔记；为已有库选择一个明确的可见项目目录作为视图位置。具体显示与同步依现有库配置核对，首版不依赖隐藏目录插件或修改配置。

[官方链接格式](https://obsidian.md/help/links)支持 Wiki 链接和 Markdown 链接，[Templates](https://obsidian.md/help/plugins/templates) 可以插入已有模板。Rondel 的共享模板是正文骨架，正式记录的 YAML 由记录脚本生成；如希望作为 Obsidian 原生模板使用，应复制到用户已选模板目录并保留适当的平铺属性，不自动写入真实库。

## 导出与研究者批注

`scripts/note_views.py` 支持 `markdown` 和 `obsidian` 两种格式，导出当前 Init 或对象记录到明确的笔记目录。文件名使用可读名称与稳定短标识，同目录已导出的关联对象生成相应链接；尚未导出的引用保留可定位标识。正文原有相对路径仍按主档案理解，外部来源和附件按原位置核对，首版不复制整套知识库或附件。

```text
python <skill>/scripts/note_views.py --root <workspace> export --note <archive-relative-record.md> --destination <visible-notes-folder> --format obsidian
python <skill>/scripts/note_views.py --root <workspace> capture --view <edited-view.md> --source <actual-user-source.yaml>
python <skill>/scripts/note_views.py --root <workspace> status
```

导出清单保存在 `.rondal/.state/note-views.json`，用身份、来源版本和摘要跟踪视图。已编辑或未登记的同名文件会被保留并报告需要审阅，Agent 不能静默覆盖；移动或重命名后先核对绑定。研究者可以在视图中批注或改写，capture 将实际修改保存为 `discussion`、`purpose: note_feedback` 的待审阅反馈，同一版本的批注只收一次。

Main 恢复相关任务或用户提示已更新笔记时，可先用 status 只读核对哪些视图有编辑、缺失或来源已更新，再定位实际修改和来源。未确认反馈处理方式时保留原状，整个检查不创建后台监听，也不把一次状态查询变成自动回写。

## 回写与共同判断

Main 读取反馈与当前主档案，指出原版本是否已变化，整理研究者的解释、修改与问题，再按实际选择调用原有更新或决定流程。视图中的状态字段或一句批注不会自动批准运行、增加预算或改变已冻结的实验方案。需要修改批准后的方案时建立关联的新方案，结果分析与稿件修订保留各自来源。

笔记视图是可以交互的副本，主档案仍是状态与证据入口；当前没有实时双向同步。未来适配其他软件时保持相同身份、来源、版本和冲突处理，只替换展示方式与必要的打开入口。模板使用见 [实验方案](../assets/templates/experiment.md)、[实验分析](../assets/templates/experiment-analysis.md)、[论文工作稿](../assets/templates/manuscript.md)与[核心论文](../assets/templates/core-paper.md)。
