# mcqa · Minecraft 整合包自动化 QA 框架

把整合包的系统级状态拿出来，用**代码断言**判通过/失败；模型不参与判分。

## 环境与安装

- Python ≥ 3.12（实测 3.14.7 通过）
- **零第三方依赖**：只用标准库（json / re / argparse / pathlib），不需要 `pip install` 任何东西
- 无需构建步骤，克隆即用

## 一条命令跑全部用例

```bash
python -m mcqa.runner run cases/ --out reports/run.json --md
```

- `--md` 同时生成 Markdown 报告（reports/run.md）
- `python -m mcqa.runner compare reports/run_round5.json reports/run_round6.json` 可对比两轮结果

## 最新一轮结果（reports/run_round6，2026-10-21）

**18 个用例：14 通过 / 3 失败 / 1 待定**。逐条结论都写在报告里，失败不藏：

| 用例 | 结果 | 原因（来自 reports/ 的真实日志） |
|---|---|---|
| RPG-LOOT-01 数据层无解析错误 | FAIL | 日志里 20 条 `ERROR`：ForgeHooks 解析不了第三方模组的注入掉落表（goety_revelation / keegsweapons / irons_spellbooks 的 chest 注入）——是模组数据包的问题，不是本框架误报 |
| RPG-LOOT-02 掉落表零解析错误 | FAIL | 同源：`Couldn't parse element loot_tables` 命中 4 处，上限设 0 所以判 FAIL |
| RPG-RECIPE-01 配方零解析错误 | FAIL | `Error parsing recipe` 命中 3 处（goety:ritual 仪式配方等）→ JEI 查不到、做不出来 |
| RPG-PERSIST-01 死亡后职业数据仍存在 | PENDING | 需要游戏内驱动层才能自动判定；已手工实测两次（persistentData 顶层不丢），等驱动层接入转正 |

> **重跑注意**：你现在跑大概率得到 **13/18**，比上表少 RPG-FRESH-01。这不是退化——FRESH-01 是新鲜度元测试，探针快照（latest.log）超过 60 分钟就会判失效，防止拿陈旧数据假装全过。要复现 14/18，用 run_round6 同期的日志快照跑即可。

## 架构三层

1. **采集**：KubeJS 脚本 (qa_probe.js) 读游戏内状态（不判定）
2. **传输**：状态 JSON 分块写入 latest.log（`[QA] i/n`），绕过 KubeJS 文件 IO 限制
3. **判定**：Python 纯函数 oracle (mcqa/asserts.py)

## 为什么不用现成方案（已知限制）

- **DebugBridge**（游戏内执行）：只有 Fabric 版，本项目是 Forge 1.20.1
- **Mineflayer**（协议机器人）：Forge 服务端拒绝 vanilla 客户端（NetworkRegistry 声道不支持）
- **直接写文件**：KubeJS 的 class filter 禁止 java.io.File / java.nio.file.Paths

所以采集层只能走日志分块这条土路——这是限制，不是设计偏好。

## 特点

- **两次推翻自己结论**：日志切分口径、以及「死亡丢数据」这条 P0 经对照实验证明不成立后主动撤销
- 用例带元测试（探针可用性、状态新鲜度），防止采集层坏了导致断言全部假通过

## 目录

- `mcqa/asserts.py` — 8 种断言
- `mcqa/runner.py` — CLI（支持 `--compare` 对比两轮）
- `cases/` — 18 条用例
- `reports/` — 各轮报告
