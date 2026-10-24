# QA 运行报告

生成时间：2026-10-24T16:46:58

| 用例 | 结果 | 失败类 | 说明 |
|---|---|---|---|
| RPG-ASSET-01 武器未被吞（storedWeapon 与背包一致） | PASS | - | T8 #2/#3：小精灵消失时武器进 storedWeapon，若 onLogi |
| RPG-CLASS-01 职业状态自洽（不变量） | PASS | - | classId/advancementCount/阶段三者必须互相对得上；对不上 |
| RPG-CRASH-01 启动无致命错误 | PASS | - | 启动期不应出现 FATAL / crash-report |
| RPG-DUP-01 无重复全局声明 | PASS | - | 防回归：ADVANCEMENT_MAP / STAT_NAMES 曾重复声明 |
| RPG-ECON-01 任务币字段可读且非负 | PASS | - | economy.js 用 questCoins 做货币；读不到说明存储被覆盖或初 |
| RPG-FRESH-01 状态新鲜度 | PASS | - | 探针数据超过 60 分钟则判定可能失效（防陈旧数据悄悄通过） |
| RPG-INIT-01 玩家数据初始化完整 | PASS | - | class_system.js 的 initPlayerData 必须把 8 个 |
| RPG-LOAD-01 全部脚本加载成功（无错误） | PASS | - | 防回归：曾 Loaded 4/6 with 2 errors；现在脚本数会变，只 |
| RPG-LOG-01 运行期无 KubeJS 脚本异常 | PASS | - | 自定义脚本每 tick 抛异常会同时毁性能与状态 |
| RPG-LOOT-01 数据层无解析错误 | PASS | - | loot_tables / 配方等解析失败 = 结构箱子空、奖励错乱 |
| RPG-LOOT-02 掉落表零解析错误 | PASS | - | 5 个掉落表解析失败 = 结构箱子空 |
| RPG-PERSIST-01 死亡/跨维度后职业数据仍存在（需驱动层） | PENDING | - | 已手工实测两次：本包死亡后 persistentData 顶层不丢，缺陷 5 撤 |
| RPG-PROBE-01 探针分块完整 | PASS | - | [QA] begin 与 end 成对，否则状态会残缺 |
| RPG-RECIPE-01 配方零解析错误 | PASS | - | 5 个配方解析失败 = JEI 查不到、做不出来 |
| RPG-REG-01 自定义物品全部注册成功 | PASS | - | register_items.js 注册的 kubejs:* 物品若缺失，技能/ |
| RPG-SCRIPT-01 职业与技能树脚本均已加载 | PASS | - | class_system.js / class_ui.js 曾整体未加载 |
| RPG-STATE-01 游戏内状态可导出 | PASS | - | qa_probe.js 能读到玩家 NBT / 阶段 / 物品注册情况（探针自检 |
| RPG-TICK-01 无 weapon_system 运行期异常 | PASS | - | 防回归：697 行曾每秒抛 LevelKJS 异常 |

合计 **17/18** 通过，1 待定

## 与上一轮对比（reports/run_workflow.json）

| 变化 | 数量 |
|---|---|
| 新增用例 | 0 |
| 修复 | 4 |
| 退化 | 0 |
| 仍失败 | 0 |
| 仍通过 | 13 |

| 用例 | 上一轮 | 本轮 | 变化 |
|---|---|---|---|
| RPG-FRESH-01 | FAIL | PASS | FIXED |
| RPG-LOOT-01 | FAIL | PASS | FIXED |
| RPG-LOOT-02 | FAIL | PASS | FIXED |
| RPG-RECIPE-01 | FAIL | PASS | FIXED |


## 失败细节

### RPG-PERSIST-01 死亡/跨维度后职业数据仍存在（需驱动层）
