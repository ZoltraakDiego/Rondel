# 资源汇总辅助脚本

`scripts/resources.py` 读取当前项目的机器资源卡，保留远程路径字符串，给出候选机器与未通过的原因。它不连接远程机器、不查询硬件、不提交任务，也不创建资源预留；真实观测与执行使用用户当前可用的连接方式。默认观测有效窗口为一小时，可按任务调整，执行前仍需复核。

机器卡由 `records.py` 创建 `kind: resource`，额外字段可按下面的结构填写，内容来自实际观测。示例是虚构数据，不能作为现有机器或空闲 GPU 的依据。

```yaml
purpose: machine
host_id: lab-a
transport: ssh
connection_ref: existing-lab-alias
system: linux
locations:
  code: /srv/project
  data: /data/videos
  environment: /srv/envs/research
  artifacts: /srv/results/project
observation:
  at: '2026-10-25T12:00:00+00:00'
  availability: available
  source: synthetic/device-observation
  gpus:
    - id: '0'
      available: true
      free_memory_gb: 24
```

观测来源、时间、可用性、资源卡核验状态与连接入口都参与候选筛选。显存要求按每个可用设备核对，不能将多张卡的显存简单相加；模型并行等特殊需求由实际方案另行核对。机器数据和环境是否满足研究任务，仍需结合数据卡、环境卡与路径绑定判断。

```text
python <skill>/scripts/resources.py --root <workspace> --gpu-count 1 --gpu-memory-gb 20 --out .state/resources/inventory.json
```

不指定 `--out` 时只读并输出简洁计数，指定后结构化汇总只写到项目 `.rondel/.state/resources/` 内。未知、陈旧、未来时间、未核验或缺少来源的观测不会成为可用候选，连接异常也不会触发回退本机。完整职责见 [资源聚合层](resource-aggregation.md)。
