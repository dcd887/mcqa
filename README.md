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

## 最新一轮结果（reports/run_fixed，2026-10-24）

**18 个用例：17 通过 / 0 失败 / 1 待定**。逐条结论都写在报告里，失败不藏。

修前是 13 通过 / 4 失败 / 1 待定，4 条失败全部定位并修掉：

| 用例 | 修前 | 现在 | 原因与修法（来自 reports/ 与 latest.log 的真实日志） |
|---|---|---|---|
| RPG-FRESH-01 状态新鲜度 | FAIL | PASS | 探针快照超 60 分钟即判失效，属**设计行为**；进一次世界让 `qa_probe.js` 重写状态即可 |
| RPG-LOOT-02 掉落表零解析错误 | FAIL（4 处） | PASS（0） | 4 张掉落表引用了**未安装**的 mod 物品（farmersdelight / nethersdelight）+ 1 个 pool 缺 `entries` + 用了 1.20.5+ 才有的 `set_written_book_pages`；用 `kubejs/data` 同名覆盖修好 |
| RPG-RECIPE-01 配方零解析错误 | FAIL（3 处） | PASS（0） | 3 个配方引用缺席的 enigmaticaddons / enigmaticlegacy；其中 `blessing_scroll` 的结果物品本身也没注册 |
| RPG-LOOT-01 数据层无解析错误 | FAIL（20 条 ERROR） | PASS（0，噪声 15） | 9 条是第三方 mod 的**进度 JSON**（`display.icon` 用了 1.20.5+ 的 `id` 写法、malum 三个空壳文件）；其余 6 类为网络检查 / JEI 渲染不兼容等噪声，已进 `NOISE_RULES` 且逐条注明了理由 |
| RPG-PERSIST-01 死亡后职业数据仍存在 | PENDING | PENDING | 需要游戏内驱动层才能自动判定；已手工实测两次（persistentData 顶层不丢）。DebugBridge 只有 Fabric 版、Forge 装不进，故长期 PENDING |

> **重跑注意**：FRESH-01 是新鲜度元测试，探针快照（latest.log）超过 60 分钟就会判失效——这是防止拿陈旧数据假装全过的设计，不是退化。复跑前先让游戏进一次世界。
>
> **噪声白名单的口径**：`NOISE_RULES` 匹配的是日志 **msg**，不是 logger 名（写 logger 名的正则永远不生效）。每条规则都写了"为什么不算失败"，不放宽到能藏住真实数据错误——配方/掉落表的解析错由 LOOT-02 与 RECIPE-01 单独守。

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
