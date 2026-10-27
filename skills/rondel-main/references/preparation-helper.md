# 前期跟踪辅助脚本

`scripts/preparation.py` 复用 records.py 的身份、排他锁、历史、摘要和中断恢复。它提供准备总表、设置草案与冻结版本、Todo 和变更影响记录，不执行研究模型或远程任务。正式进入 Pre 初始化一次，恢复时读取既有进度；单项论文或技术问答无需重新初始化整轮项目。

```text
python <skill>/scripts/preparation.py --root <workspace> init --source <actual-source.yaml>
python <skill>/scripts/preparation.py --root <workspace> status
python <skill>/scripts/preparation.py --root <workspace> setting --request <setting.yaml>
python <skill>/scripts/preparation.py --root <workspace> freeze --request <freeze.yaml>
python <skill>/scripts/preparation.py --root <workspace> revise --request <revision.yaml>
python <skill>/scripts/preparation.py --root <workspace> task --request <task.yaml>
python <skill>/scripts/preparation.py --root <workspace> pin --note <record.md> --out .state/preparation/pin.json
python <skill>/scripts/preparation.py --root <workspace> changelog
python <skill>/scripts/preparation.py --root <workspace> report
```

setting 请求使用 key、purpose、name、spec、body 和可选 refs。key 是当前用途，purpose 为 dataset、protocol、baseline 或 environment，未知定义可以先作为空草案。下面是虚构结构，实际内容需要按来源填写；setting 后由正常 transition 把核对完成的资源改为 checked，再调用 freeze。

```yaml
key: primary-evaluation
purpose: protocol
name: 当前主评价协议
spec:
  split_source: 实际划分来源与摘要
  supervision: 实际训练与适配可见信息
  evaluation: 实际指标实现、聚合单位与模型选择来源
body: |
  # 当前主评价协议
  记录实际核验依据、比较范围与仍影响解释的条件。
refs: []
```

freeze 使用 relative、expected、source 和 reason；expected 是当前设置文件的实际 SHA256，source 按 [人的决定](decisions.md) 保存真实来源。revise 额外需要完整的新 spec 与 impact_review，可选 body 省略时沿用旧正文。impact_review 至少包含 summary，按实际受影响对象在 results 中给出 action 与 reason，keep 表示已核对并保留旧结果的解释。

```yaml
relative: setup/resources/<actual-record-id>.md
expected: <sha256-after-rereading>
source:
  kind: user_message
  reference: 实际用户回复位置
  quote: 实际选择与变更范围的原话
reason: 实际修改原因
spec:
  split_source: 新的实际划分来源与摘要
  supervision: 沿实际方案填写
  evaluation: 沿实际方案填写
impact_review:
  summary: 哪项条件变了，哪些比较需要重新核对
  results:
    'record:<affected-id>':
      action: recheck
      reason: 具体影响与下一项检查
```

每次实际运行的 fields.setting_refs 保存 pin 生成的映射列表。映射包含 ref、version、definition_sha256，正式结果不能引用草案或不存在的版本，已批准方案和已准备或执行的运行不能事后改绑。完整记录请求仍通过 records.py 创建，设置引用与普通 refs 可以一起使用。

Todo 的 task 请求包含 key、state、evidence、note、expected 和可选 source。expected 对应总表最新摘要，evidence 为当前项目的记录引用列表；waived 需要真实用户来源。总表 focus 的修改使用正常 update 请求，保留其他字段，关联痛点和问题记录，当前主问题通过正常人的状态转换进入 active。

status、changelog 和 pin 的读取阶段保持只读，pin 的输出限定到 `.state/preparation/` JSON 文件。report 显式重建两个可读 Markdown 投影，不改科学状态；恢复中断使用 records.py recover。相同设置的定义冻结后保持不变，运行观测可以独立更新，完整合同见 [前期跟踪](pre-tracking.md)。

status 的 pre_review_tasks_complete 统计九项常规准备任务，排除 phase_review，checklist_complete 仍包含全部十项。它们不选择退出结果或自动改阶段；Main 可以在资料齐备、到评审点或用户提出时按 [退出流程](pre-exit.md) 组织讨论。实际评审、带入项和首轮任务保存到正常 discussion 与 decision 中。
