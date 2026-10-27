# 两份研究包的文件导出

`scripts/closeout.py` 对明确文件清单做只读计划、新建导出和文件完整性核对。输出固定在用户工作区 `.rondel/deliverables/<release-id>/`，已有版本不覆盖。脚本不执行包中的命令，不下载引用，不更改项目阶段或原文件，实际复现程度写在相应 README 和验证记录中。

```text
python <skill>/scripts/closeout.py --root <workspace> plan --request <selected-files.json>
python <skill>/scripts/closeout.py --root <workspace> build --request <selected-files.json>
python <skill>/scripts/closeout.py --root <workspace> verify --release <release-id>
```

请求为 JSON，release_id 使用小写字母、数字、连字符或下划线。items 中每项指定 package（reproduction 或 materials）、source（显式本地文件，或相对 `.rondel` 的路径）和 target（包内相对路径，使用正斜杠）。两个包分别需要一份实际 README.md，目录、通配符和符号链接不作为复制项，所有文件逐项选定。

```json
{
  "release_id": "research-v1",
  "items": [
    {"package": "reproduction", "source": "paper/reproduction-readme.md", "target": "README.md"},
    {"package": "materials", "source": "paper/materials-readme.md", "target": "README.md"}
  ],
  "references": [
    {"package": "reproduction", "location": "host-a:/research/weights/model.pt", "description": "实际权重入口，获取条件与核验见 README"}
  ]
}
```

manifest.json 保存实际复制文件的目标路径、字节数和 SHA256，以及显式外部引用，不自动写入本机绝对来源位置。plan 不写文件，build 先核对全部输入再新建目录；复制中断的目录原样保留，未生成 manifest 的版本按未完成处理，核对后使用新 release_id 重建。verify 只报告内容是否与清单一致，返回 reproduction_verified: false 和 references_fetched: false，不把文件摘要当成研究验证。

外部引用的可达性、内容或版本仍需实际证据，链接、附件、数据许可与交付对象按 [收尾流程](post-closeout.md) 核对。包内公开程度和匿名性由当前材料审阅确定，脚本不会自动匿名化或识别所有私人内容。可先完成内部包，再按明确对象选择分享材料。
