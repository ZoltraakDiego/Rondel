# 有限清单与证据辅助检查

`scripts/evidence.py` 只读核对当前 experiment 的实际批准来源、冻结范围、设置引用和已登记尝试。它不连接实验机、不提交任务，不判断研究结论，也不把结构通过当成新的执行授权。实际代码、配置、数据、评价与资源核验仍由 mid.preflight 和当前工具完成。

```text
python <skill>/scripts/evidence.py --root <workspace> preflight --experiment <experiment-id>
python <skill>/scripts/evidence.py --root <workspace> preflight --experiment <experiment-id> --out .state/evidence/preflight.json
```

默认只输出结构结果、计数和问题，不写项目文件；显式 out 限定在 `.state/evidence/` 的 JSON 报告。structural_ready 表示这些记录条件通过，live_checks_required 列出实际仍需确认的类别。已有 planned/ready 记录通过 pending_run_refs 接续，queued/running 属于已登记活动，不因此重复提交。

新方案的 scope.run_keys 是有限且唯一的运行标识，例如 baseline-s42、adapter-s42。max_attempts_per_run 默认 1，max_total_attempts 默认标识数量，均计算登记的尝试；新尝试需要预算且同一 key 前次已经 failed/cancelled，或 completed 后有 run_inspection 依据标为 invalid。种子或条件不同使用不同 key，失败保留原记录，不能覆盖旧 run。

每次 run 保存 experiment_ref、run_key、attempt 和与方案一致的 setting_refs。关联方案通过 approved 或适用后续执行状态核对，实际 scope 与 approval.scope 必须一致。旧方案没有有限标识时报告需核对，不推断任意范围，也不改动历史记录。

required_setting_purposes 默认是 dataset、protocol、baseline、environment；不适用条件放在具体获准方案中明确。引用设置需 frozen、checked 且定义匹配，采用新版后的旧方案需要相应影响审阅；新版 impact_review.results 中针对该方案的 keep 与具体理由可保留原条件。历史结果继续对应原版本，结构检查不会作废或改绑它们。
