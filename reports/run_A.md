# QA 运行报告

生成时间：2026-10-20T17:51:18

| 用例 | 结果 | 失败类 | 说明 |
|---|---|---|---|
| RPG-ASSET-01 武器未被吞（storedWeapon 与背包一致） | PASS | - | T8 #2/#3：小精灵消失时武器进 storedWeapon，若 onLogi |
| RPG-CLASS-01 职业状态自洽（不变量） | PASS | - | classId/advancementCount/阶段三者必须互相对得上；对不上 |
| RPG-CRASH-01 启动无致命错误 | PASS | - | 启动期不应出现 FATAL / crash-report |
| RPG-DUP-01 无重复全局声明 | PASS | - | 防回归：ADVANCEMENT_MAP / STAT_NAMES 曾重复声明 |
| RPG-ECON-01 任务币字段可读且非负 | PASS | - | economy.js 用 questCoins 做货币；读不到说明存储被覆盖或初 |
| RPG-FRESH-01 状态新鲜度 | PASS | - | 探针数据超过 60 分钟则判定可能失效（防陈旧数据悄悄通过） |
| RPG-INIT-01 玩家数据初始化完整 | PASS | - | class_system.js 的 initPlayerData 必须把 8 个 |
| RPG-LOAD-01 六个脚本全部加载成功 | PASS | - | 防回归：曾 Loaded 4/6 with 2 errors |
| RPG-LOG-01 运行期无 KubeJS 脚本异常 | PASS | - | 自定义脚本每 tick 抛异常会同时毁性能与状态 |
| RPG-LOOT-01 数据层无解析错误 | FAIL | LOG_ERROR | loot_tables / 配方等解析失败 = 结构箱子空、奖励错乱 |
| RPG-LOOT-02 掉落表零解析错误 | FAIL | SCRIPT_ERROR | 5 个掉落表解析失败 = 结构箱子空 |
| RPG-PERSIST-01 职业数据放在可持久子标签里 | FAIL | SCRIPT_ERROR | Forge 只保留 persistentData.PlayerPersisted |
| RPG-PROBE-01 探针分块完整 | PASS | - | [QA] begin 与 end 成对，否则状态会残缺 |
| RPG-RECIPE-01 配方零解析错误 | FAIL | SCRIPT_ERROR | 5 个配方解析失败 = JEI 查不到、做不出来 |
| RPG-REG-01 自定义物品全部注册成功 | PASS | - | register_items.js 注册的 kubejs:* 物品若缺失，技能/ |
| RPG-SCRIPT-01 职业与技能树脚本均已加载 | PASS | - | class_system.js / class_ui.js 曾整体未加载 |
| RPG-STATE-01 游戏内状态可导出 | PASS | - | qa_probe.js 能读到玩家 NBT / 阶段 / 物品注册情况（探针自检 |
| RPG-TICK-01 无 weapon_system 运行期异常 | PASS | - | 防回归：697 行曾每秒抛 LevelKJS 异常 |

合计 **14/18** 通过，0 待定

## 失败细节

### RPG-LOOT-01 数据层无解析错误
- `log_clean` 失败：`{"counts": {"fatal": 0, "script": 0, "error": 30, "noise_ignored": 0}, "samples": [{"line": 16, "level": "ERROR", "logger": "net.minecraftforge.common.ForgeHooks/", "msg": "Couldn't parse element loot_tables:irons_spellbooks:chests/catacombs/crypt_loot"}, {"line": 65, "level": "ERROR", "logger": "net.minecraftforge.common.ForgeHooks/", "msg": "Couldn't parse element loot_tables:goety_revelation:inject/chests/goety_revelation/church_food"}, {"line": 121, "level": "ERROR", "logger": "net.minecraftforge.common.ForgeHooks/", "msg": "Couldn't parse element loot_tables:keegsweapons:inject/chests/anc`
  计数：{'fatal': 0, 'script': 0, 'error': 30, 'noise_ignored': 0}
  - L16 [ERROR] `net.minecraftforge.commo` Couldn't parse element loot_tables:irons_spellbooks:chests/catacombs/crypt_loot
  - L65 [ERROR] `net.minecraftforge.commo` Couldn't parse element loot_tables:goety_revelation:inject/chests/goety_revelation/church_food
  - L121 [ERROR] `net.minecraftforge.commo` Couldn't parse element loot_tables:keegsweapons:inject/chests/ancient_city
  - L157 [ERROR] `net.minecraftforge.commo` Couldn't parse element loot_tables:irons_spellbooks:chests/citadel/citadel_tomes

### RPG-LOOT-02 掉落表零解析错误
- `log_match` 失败：`{"pattern": "Couldn't parse element loot_tables", "hits": 5, "expect_min": null, "expect_max": 0, "kind": "SCRIPT_ERROR", "samples": ["[2010月2026 17:23:30.302] [Worker-ResourceReload-64/ERROR] [net.minecraftforge.common.ForgeHooks/]: Couldn't parse element loot_tables:irons_spellbooks:chests/catacombs/crypt_loot", "[2010月2026 17:23:30.315] [Worker-ResourceReload-64/ERROR] [net.minecraftforge.common.ForgeHooks/]: Couldn't parse element loot_tables:goety_revelation:inject/chests/goety_revelation/church_food", "[2010月2026 17:23:30.793] [Worker-ResourceReload-64/ERROR] [net.minecraftforge.common.F`

### RPG-PERSIST-01 职业数据放在可持久子标签里
- `state` 失败：`{"failed": [{"path": "persistentData.PlayerPersisted", "op": "exists", "want": null, "got": null}], "kind": "SCRIPT_ERROR", "probe_errors": []}`

### RPG-RECIPE-01 配方零解析错误
- `log_match` 失败：`{"pattern": "Error parsing recipe", "hits": 5, "expect_min": null, "expect_max": 0, "kind": "SCRIPT_ERROR", "samples": ["[2010月2026 17:23:31.229] [KubeJS Recipe Event Worker 0/WARN] [KubeJS Server/]: Error parsing recipe forbidden_arcanus:edelwood_chest_boat[minecraft:crafting_shapeless]: {\"type\":\"minecraft:crafting_sha", "[2010月2026 17:23:31.229] [KubeJS Recipe Event Worker 0/WARN] [KubeJS Server/]: Error parsing recipe forbidden_arcanus:aurum_chest_boat[minecraft:crafting_shapeless]: {\"type\":\"minecraft:crafting_shapel", "[2010月2026 17:23:31.232] [KubeJS Recipe Event Worker 0/WARN] [Kub`
