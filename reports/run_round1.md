# QA 运行报告

生成时间：2026-10-20T17:07:51

| 用例 | 结果 | 失败类 | 说明 |
|---|---|---|---|
| RPG-ASSET-01 武器未被吞（storedWeapon 与背包一致） | PASS | - | T8 #2/#3：小精灵消失时武器进 storedWeapon，若 onLogi |
| RPG-CLASS-01 职业状态自洽（不变量） | PASS | - | classId/advancementCount/阶段三者必须互相对得上；对不上 |
| RPG-CRASH-01 启动无致命错误 | PASS | - | 启动期不应出现 FATAL / crash-report |
| RPG-ECON-01 任务币字段可读且非负 | PASS | - | economy.js 用 questCoins 做货币；读不到说明存储被覆盖或初 |
| RPG-INIT-01 玩家数据初始化完整 | PASS | - | class_system.js 的 initPlayerData 必须把 8 个 |
| RPG-LOG-01 运行期无 KubeJS 脚本异常 | FAIL | SCRIPT_ERROR | 自定义脚本每 tick 抛异常会同时毁性能与状态 |
| RPG-LOOT-01 数据层无解析错误 | FAIL | SCRIPT_ERROR | loot_tables / 配方等解析失败 = 结构箱子空、奖励错乱 |
| RPG-PERSIST-01 职业数据放在可持久子标签里 | FAIL | SCRIPT_ERROR | Forge 只保留 persistentData.PlayerPersisted |
| RPG-REG-01 自定义物品全部注册成功 | PASS | - | register_items.js 注册的 kubejs:* 物品若缺失，技能/ |
| RPG-STATE-01 游戏内状态可导出 | PASS | - | qa_probe.js 能读到玩家 NBT / 阶段 / 物品注册情况（探针自检 |

合计 **7/10** 通过，0 待定

## 失败细节

### RPG-LOG-01 运行期无 KubeJS 脚本异常
- `log_clean` 失败：`{"counts": {"fatal": 0, "script": 140083, "error": 127, "noise_ignored": 41}, "samples": [{"line": 1274, "level": "ERROR", "logger": "KubeJS Server/", "msg": "TypeError: TypeError: redeclaration of const ADVANCEMENT_MAP."}, {"line": 1275, "level": "ERROR", "logger": "KubeJS Server/", "msg": "TypeError: TypeError: redeclaration of const STAT_NAMES."}, {"line": 2524, "level": "ERROR", "logger": "KubeJS Server/", "msg": "weapon_system.js#697: Error in 'PlayerEvents.tick': Can't find method dev.latvian.mods.kubejs.core.LevelKJS.kjs$getEntitiesWithin(net.minecraft.server.level.ServerPlayer,number).`
  计数：{'fatal': 0, 'script': 140083, 'error': 127, 'noise_ignored': 41}
  - L1274 [ERROR] `KubeJS Server/` TypeError: TypeError: redeclaration of const ADVANCEMENT_MAP.
  - L1275 [ERROR] `KubeJS Server/` TypeError: TypeError: redeclaration of const STAT_NAMES.
  - L2524 [ERROR] `KubeJS Server/` weapon_system.js#697: Error in 'PlayerEvents.tick': Can't find method dev.latvian.mods.kubejs.core.LevelKJS.kjs$getEntit

### RPG-LOOT-01 数据层无解析错误
- `log_clean` 失败：`{"counts": {"fatal": 0, "script": 140131, "error": 127, "noise_ignored": 41}, "samples": [{"line": 1086, "level": "ERROR", "logger": "placebo/", "msg": "Exception loading patreon trails data!"}, {"line": 1290, "level": "ERROR", "logger": "net.minecraftforge.common.ForgeHooks/", "msg": "Couldn't parse element loot_tables:irons_spellbooks:chests/catacombs/crypt_loot"}, {"line": 1339, "level": "ERROR", "logger": "net.minecraftforge.common.ForgeHooks/", "msg": "Couldn't parse element loot_tables:goety_revelation:inject/chests/goety_revelation/church_food"}, {"line": 1397, "level": "ERROR", "logger`
  计数：{'fatal': 0, 'script': 140131, 'error': 127, 'noise_ignored': 41}
  - L1086 [ERROR] `placebo/` Exception loading patreon trails data!
  - L1290 [ERROR] `net.minecraftforge.commo` Couldn't parse element loot_tables:irons_spellbooks:chests/catacombs/crypt_loot
  - L1339 [ERROR] `net.minecraftforge.commo` Couldn't parse element loot_tables:goety_revelation:inject/chests/goety_revelation/church_food
  - L1397 [ERROR] `net.minecraftforge.commo` Couldn't parse element loot_tables:keegsweapons:inject/chests/ancient_city

### RPG-PERSIST-01 职业数据放在可持久子标签里
- `state` 失败：`{"failed": [{"path": "persistentData.PlayerPersisted", "op": "exists", "want": null, "got": null}], "kind": "SCRIPT_ERROR", "probe_errors": []}`
