"""mcqa.oracle —— 断言层（纯函数，无网络、无 LLM）

设计原则：
1. 每个断言返回 (passed: bool, detail: dict)，detail 里必须能看出"差多少"
2. 不允许在断言里调用模型 —— 判通过/失败只能由代码做
3. 只依赖标准库
"""
from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

DEFAULT_LOG_PATTERNS = [
    r"\bException\b",
    r"\bCaused by:",
    r"crash-report",
    r"FATAL",
    r"EvaluatorException",
    r"Can't find method",
    r"java\.lang\.\w*(?:Error|Exception)",
    r"Attempted to load class",
    r"Missing or unsupported mandatory dependencies",
]

# 已知噪音：这些行即使命中关键词也不算失败（按需扩充，但要写进报告）
DEFAULT_LOG_ALLOW = [
    r"RealmsClient",
    r"Could not authorize you against Realms",
    r"version check",
    r"Failed to fetch",
]


class FailureKind(str, Enum):
    RECIPE_MISSING = "RECIPE_MISSING"
    RESOURCE_TIMEOUT = "RESOURCE_TIMEOUT"
    GUI_MISMATCH = "GUI_MISMATCH"
    CRASH = "CRASH"
    LAG = "LAG"
    NAV_FAIL = "NAV_FAIL"
    LOG_ERROR = "LOG_ERROR"
    SCRIPT_ERROR = "SCRIPT_ERROR"
    ORACLE_FALSE_ALARM = "ORACLE_FALSE_ALARM"



def _read_text(path: str | Path) -> str:
    """Minecraft 日志在中文 Windows 上常是 GBK；先试 UTF-8，坏字符多则回退 GB18030。"""
    raw = Path(path).read_bytes()
    for enc in ("utf-8", "gb18030"):
        try:
            txt = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        bad = txt.count("\ufffd")
        if bad == 0 or enc == "gb18030":
            return txt
    return raw.decode("utf-8", errors="replace")


def _ok(detail: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
    return True, detail or {}


def _fail(detail: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    return False, detail


# ---------------------------------------------------------------- 背包 / 物品
def assert_inv(snapshot: Dict[str, Any], item_id: str, min_count: int = 1) -> Tuple[bool, Dict[str, Any]]:
    """snapshot: {"inv": [{"id": "...", "count": n}, ...]}"""
    items = snapshot.get("inv") or []
    total = sum(int(i.get("count", 0)) for i in items if _same_item(i.get("id"), item_id))
    if total >= min_count:
        return _ok({"item": item_id, "got": total, "want": min_count})
    return _fail({"item": item_id, "got": total, "want": min_count, "kind": FailureKind.RESOURCE_TIMEOUT.value})


def _same_item(a: Optional[str], b: str) -> bool:
    if not a:
        return False
    a, b = a.strip().lower(), b.strip().lower()
    if a == b:
        return True
    # 允许省略命名空间
    return (":" not in b and a.endswith(":" + b)) or (":" not in a and b.endswith(":" + a))


# ---------------------------------------------------------------- 日志
LINE_RE = re.compile(r"^\[(?P<ts>[^\]]+)\] \[(?P<thread>[^/]+)/(?P<level>[A-Z]+)\] \[(?P<logger>[^\]]*)\]: (?P<msg>.*)$")

# 启动期可选依赖探测：这是 mod 的正常行为，不算失败
NOISE_RULES = [
    (re.compile(r"^Error loading class: .*(ClassNotFoundException|NoClassDefFoundError)"), "mixin-probe"),
    (re.compile(r"Realms"), "realms"),
    (re.compile(r"Failed to fetch|Could not authorize"), "network-probe"),
    (re.compile(r"version check|UpdateChecker"), "update-probe"),
    (re.compile(r"Failed to retrieve the latest mod versions"), "update-probe"),
    (re.compile(r"Failed to retrieve profile key pair"), "offline-profile"),
    (re.compile(r"Exception loading patreon wing data"), "cosmetic"),
    (re.compile(r"Couldn't find .* on the client"), "client-only-compat"),
]


_TS_RE = re.compile(r"^\[([^\]]+)\]")


def _ts_of(line: str):
    """取出 'HH:MM:SS.mmm'（保留毫秒，用于同秒内的先后区分）。"""
    m = _TS_RE.match(line.strip())
    if not m:
        return None
    tok = m.group(1).split()[-1]
    return tok if "." in tok else tok + ".000"


def _ts_ms(ts: str):
    """'HH:MM:SS.mmm' -> 毫秒整数（同一天内比较足够）。"""
    try:
        hh, mm, rest = ts.split(":")
        ss, ms = rest.split(".")
        return ((int(hh) * 3600) + int(mm) * 60 + int(ss)) * 1000 + int(ms)
    except Exception:
        return None


def _cut_at_last_reload(text: str) -> str:
    """只保留"最后一次脚本加载"之后的日志。

    切点选择（三次踩坑后的结论）：
    1) 不能按汇总行 "Loaded N/M KubeJS server scripts" 切 —— 逐文件加载行在它之前，会被切掉
    2) 不能只到秒 —— 旧脚本报错可能和新加载同一秒（实测 .058 报错 vs .965 加载）
    3) 逐文件加载行中间会夹别的日志，不能用"连续块"回溯
    最终做法：以汇总行时间为锚点，往前取 3 秒窗口内**最早的一条逐文件加载行**作为切点。
    """
    lines = text.splitlines()

    anchor_ms = None
    for i in range(len(lines) - 1, -1, -1):
        if "KubeJS server scripts" in lines[i] and "Loaded" in lines[i]:
            anchor_ms = _ts_ms(_ts_of(lines[i]) or "")
            break

    cand = []
    for i, ln in enumerate(lines):
        if "Loaded script server_scripts:" not in ln:
            continue
        ms = _ts_ms(_ts_of(ln) or "")
        if ms is None:
            continue
        if anchor_ms is None or (0 <= anchor_ms - ms <= 3000):
            cand.append(ms)
    cut_ms = min(cand) if cand else anchor_ms
    if cut_ms is None:
        return text

    for i, ln in enumerate(lines):
        ms = _ts_ms(_ts_of(ln) or "")
        if ms is not None and ms >= cut_ms:
            return "\n".join(lines[i:])
    return text


EXC_HINT = re.compile(r"(Exception|Error:|Caused by:|\bat .*\(.*\.java:\d+\))")


def parse_log(text: str) -> List[Dict[str, Any]]:
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        m = LINE_RE.match(line.strip())
        if m:
            out.append({"line": i, "level": m.group("level"), "logger": m.group("logger"),
                        "msg": m.group("msg"), "raw": line.strip()})
        elif out and EXC_HINT.search(line):
            # 续行（堆栈）挂到上一行
            out[-1]["raw"] += "\n" + line.strip()
    return out


def scan_log(text: str, since_marker: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """since_marker：只看日志里最后一次出现该字符串之后的记录（默认按"最后一次 reload"切）"""
    """把日志切成四类：
    fatal       —— FATAL / crash-report
    script      —— KubeJS / Rhino 的运行期脚本错误（高信号，通常就是整合包作者的 bug）
    error       —— 其它 ERROR 级异常
    noise       —— 可忽略（可选依赖探测 / Realms / 更新检查）
    """
    if since_marker:
        text = _cut_at_last_reload(text)
    lines = text.splitlines()
    buckets: Dict[str, List[Dict[str, Any]]] = {"fatal": [], "script": [], "error": [], "noise": []}
    for rec in parse_log("\n".join(lines)):
        msg = rec["msg"]
        if any(rx.search(msg) for rx, _ in NOISE_RULES):
            buckets["noise"].append(rec)
            continue
        is_exc = bool(EXC_HINT.search(msg)) or bool(EXC_HINT.search(rec.get("raw", "")))
        if rec["level"] in ("FATAL",) or "crash-report" in msg.lower():
            buckets["fatal"].append(rec)
        elif "Error parsing recipe" in msg or "Error parsing loot" in msg:
            buckets["error"].append(rec)          # WARN 级但属于数据层硬错
        elif rec["level"] == "ERROR" and (is_exc or "KubeJS" in rec["logger"] or "Rhino" in rec["logger"]):
            if "KubeJS" in rec["logger"] or "Rhino" in rec["logger"]:
                buckets["script"].append(rec)
            else:
                buckets["error"].append(rec)
        elif rec["level"] == "ERROR":
            buckets["error"].append(rec)
    return buckets


def assert_log_clean(
    log_path: str | Path,
    max_hits: int = 0,
    sample: int = 6,
    allow_script: bool = False,
    only: Optional[str] = None,
    since_marker: Optional[str] = "KubeJS server scripts",
) -> Tuple[bool, Dict[str, Any]]:
    """判据：fatal + error（+ 可选 script）合计不超过 max_hits。
    noise 只统计数量、不判失败 —— 否则每个整合包都会因为"没装 EMI"而红。
    """
    p = Path(log_path)
    if not p.exists():
        return _fail({"log": str(p), "error": "log not found", "kind": FailureKind.CRASH.value})
    text = _read_text(p)
    b = scan_log(text, since_marker=since_marker)
    if only in ("fatal", "error", "script"):
        bad = b[only]
    else:
        bad = b["fatal"] + b["error"] + ([] if allow_script else b["script"])
    detail = {
        "counts": {"fatal": len(b["fatal"]), "script": len(b["script"]),
                   "error": len(b["error"]), "noise_ignored": len(b["noise"])},
        "samples": [{"line": r["line"], "level": r["level"], "logger": r["logger"], "msg": r["msg"][:200]}
                    for r in bad[:sample]],
    }
    if len(bad) <= max_hits:
        return True, detail
    detail["kind"] = FailureKind.SCRIPT_ERROR.value if b["script"] and not allow_script else FailureKind.LOG_ERROR.value
    detail["allow_max"] = max_hits
    return False, detail


# ---------------------------------------------------------------- tick / 卡顿
def assert_tps(tick_ms: Iterable[float], min_tps: float = 19.0) -> Tuple[bool, Dict[str, Any]]:
    vals = [float(x) for x in tick_ms if x is not None]
    if not vals:
        return _fail({"error": "no tick samples", "kind": FailureKind.LAG.value})
    avg = sum(vals) / len(vals)
    tps = 1000.0 / avg if avg > 0 else 0.0
    worst = max(vals)
    if tps >= min_tps:
        return _ok({"tps_avg": round(tps, 2), "worst_tick_ms": round(worst, 1), "samples": len(vals)})
    return _fail({"tps_avg": round(tps, 2), "min_tps": min_tps,
                  "worst_tick_ms": round(worst, 1), "samples": len(vals), "kind": FailureKind.LAG.value})


def parse_tick_samples_from_log(log_path: str | Path) -> List[float]:
    """从 Forge 的 'Can't keep up! ... running Xms behind' / 'took Xms' 行里抽 tick 时长。"""
    p = Path(log_path)
    if not p.exists():
        return []
    text = _read_text(p)
    out: List[float] = []
    for m in re.finditer(r"running (\d+)ms behind", text):
        out.append(float(m.group(1)))
    for m in re.finditer(r"Server tick took (\d+(?:\.\d+)?) ?ms", text):
        out.append(float(m.group(1)))
    return out


# ---------------------------------------------------------------- GUI
def assert_gui_slots(
    screen: Dict[str, Any],
    expect: Sequence[Dict[str, Any]],
) -> Tuple[bool, Dict[str, Any]]:
    """screen: {"slots":[{"idx":i,"item":{"itemId":"...","count":n}},...]}
    expect: [{"item_id": "...", "min_count": 1}]  按 itemId 聚合，不依赖槽位下标（版本无关）
    """
    slots = (screen or {}).get("slots") or []
    got: Dict[str, int] = {}
    for s in slots:
        it = (s or {}).get("item") or {}
        iid = it.get("itemId") or it.get("id")
        if not iid:
            continue
        got[iid] = got.get(iid, 0) + int(it.get("count", 1))
    missing = []
    for e in expect:
        want = int(e.get("min_count", 1))
        have = sum(v for k, v in got.items() if _same_item(k, e["item_id"]))
        if have < want:
            missing.append({"item": e["item_id"], "got": have, "want": want})
    if not missing:
        return _ok({"slots": len(slots), "distinct_items": len(got)})
    return _fail({"missing": missing, "kind": FailureKind.GUI_MISMATCH.value})


# ---------------------------------------------------------------- 脚本自报结果
def assert_script_pass(results: Dict[str, Any], case_id: str) -> Tuple[bool, Dict[str, Any]]:
    """KubeJS 内嵌测试脚本会把 {case, pass, detail} 写成 JSON；这里只做搬运与分类。"""
    item = None
    for r in (results or {}).get("results") or []:
        if r.get("case") == case_id:
            item = r
            break
    if item is None:
        return _fail({"case": case_id, "error": "no result from in-game script",
                      "kind": FailureKind.SCRIPT_ERROR.value})
    if item.get("pass"):
        return _ok({"case": case_id, "detail": item.get("detail")})
    return _fail({"case": case_id, "detail": item.get("detail"),
                  "kind": item.get("kind") or FailureKind.SCRIPT_ERROR.value})




# ---------------------------------------------------------------- 游戏内状态（探针导出）
def _dig(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            if part in cur:
                cur = cur[part]
            else:
                return None
        else:
            return None
    return cur


def assert_state(state: Dict[str, Any], checks: Sequence[Dict[str, Any]]) -> Tuple[bool, Dict[str, Any]]:
    """state 来自 qa_probe.js 导出的 latest.json。
    checks: [{"path": "player.xpLevel", "op": "equals|contains|truthy|min|neq", "value": ...}]
    路径用点号，数组用整数下标（如 stages.0）。
    """
    if not state:
        return _fail({"error": "no state (probe 未运行)", "kind": FailureKind.SCRIPT_ERROR.value})
    problems = []
    for c in checks:
        path = c.get("path", "")
        op = c.get("op", "truthy")
        want = c.get("value")
        got = _dig(state, path)
        exists = got is not None
        ok = False
        if op == "exists":
            ok = exists
        elif op == "truthy":
            ok = bool(got) and got != "<unreadable>"
        elif op == "equals":
            ok = str(got) == str(want)
        elif op == "neq":
            ok = str(got) != str(want)
        elif op == "contains":
            if isinstance(got, list):
                ok = any(str(want) == str(x) for x in got)
            else:
                ok = want in str(got or "")
        elif op == "min":
            try:
                ok = float(got) >= float(want)
            except (TypeError, ValueError):
                ok = False
        else:
            problems.append({"path": path, "error": "unknown op " + op})
            continue
        if not ok:
            problems.append({"path": path, "op": op, "want": want, "got": got})
    if not problems:
        return _ok({"checks": len(checks)})
    return _fail({"failed": problems, "kind": FailureKind.SCRIPT_ERROR.value,
                  "probe_errors": (state.get("errors") or [])[:5]})


def assert_items_registered(state: Dict[str, Any], allow_missing: Sequence[str] = ()) -> Tuple[bool, Dict[str, Any]]:
    """检查 qa_probe 里 PROBE_ITEMS 全部能用 Item.of 取到（= 注册成功）。"""
    items = (state or {}).get("items") or {}
    if not items:
        return _fail({"error": "state.items 为空（探针未导出）", "kind": FailureKind.SCRIPT_ERROR.value})
    if isinstance(items, dict) and "probed" in items:
        missing = [m for m in (items.get("missing") or []) if m not in allow_missing]
        checked = int(items.get("probed") or 0)
    else:
        checked = len(items)
        missing = [k for k, v in items.items() if not v and k not in allow_missing]
    if not missing:
        return _ok({"checked": checked})
    return _fail({"checked": checked, "missing": missing[:20], "missing_count": len(missing),
                  "kind": FailureKind.RECIPE_MISSING.value,
                  "probe_errors": (state.get("errors") or [])[:5]})


# ---------------------------------------------------------------- 职业系统不变量
BASIC_CLASSES = {"warrior", "mage", "ranger", "priest"}
ADVANCEMENT = {
    "warrior": {"berserker", "paladin"},
    "mage": {"elementalist", "arcanist"},
    "ranger": {"sky_archer", "shadow_hunter"},
    "priest": {"inquisitor", "high_priest"},
}
ADVANCED_CLASSES = set().union(*ADVANCEMENT.values())          # 8 个
ALL_CLASSES = BASIC_CLASSES | ADVANCED_CLASSES                 # 12 个
STAGE_PREFIX = "class_"


def assert_class_invariants(state: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """职业系统的状态不变量（依据 class_system.js）：
    1) classId 只能是空串或 12 个合法职业之一
    2) advancementCount == 0 时 classId 必须是基础职业（或空）
    3) advancementCount == 1 时 classId 必须是上位职业
    4) classId 非空时，stages 里应有 class_<classId>
    """
    if not state:
        return _fail({"error": "no state", "kind": FailureKind.SCRIPT_ERROR.value})
    f = state.get("fields") or {}
    pd = state.get("persistentData") or {}
    stages = state.get("stages") or []
    cid = str(f.get("classId") if f.get("classId") is not None else pd.get("classId", "")).strip()
    if cid in ("0", "None", "null"):
        cid = ""
    try:
        adv = int(f.get("advancementCount") or 0)
    except (TypeError, ValueError):
        adv = -1

    problems = []
    if cid and cid not in ALL_CLASSES:
        problems.append({"rule": "classId 合法", "got": cid, "allowed": sorted(ALL_CLASSES)})
    if adv not in (0, 1):
        problems.append({"rule": "advancementCount ∈ {0,1}", "got": adv})
    if cid and adv == 0 and cid not in BASIC_CLASSES:
        problems.append({"rule": "未转职时必须是基础职业", "classId": cid})
    if cid and adv == 1 and cid not in ADVANCED_CLASSES:
        problems.append({"rule": "已转职时必须是上位职业", "classId": cid})
    if cid and (STAGE_PREFIX + cid) not in stages:
        problems.append({"rule": "阶段与职业一致", "want_stage": STAGE_PREFIX + cid, "stages": stages[:12]})

    detail = {"classId": cid or "(空)", "advancementCount": adv, "stages": len(stages)}
    if not problems:
        return True, detail
    detail["problems"] = problems
    detail["kind"] = FailureKind.GUI_MISMATCH.value
    return False, detail


# ---------------------------------------------------------------- 日志模式匹配
def assert_log_match(
    log_path: str | Path,
    pattern: str,
    expect_min: Optional[int] = None,
    expect_max: Optional[int] = None,
    sample: int = 4,
    since_marker: Optional[str] = "KubeJS server scripts",
) -> Tuple[bool, Dict[str, Any]]:
    """在"最近一次 reload 之后"的日志里数某个正则的命中次数，按上下界判定。
    典型用法：
      - 加载成功：pattern="Loaded 6/6 KubeJS server scripts", expect_min=1
      - 零错误：  pattern="redeclaration", expect_max=0
    """
    p = Path(log_path)
    if not p.exists():
        return _fail({"log": str(p), "error": "log not found", "kind": FailureKind.CRASH.value})
    text = _read_text(p)
    if since_marker:
        text = _cut_at_last_reload(text)
    hits = [m.group(0) for m in re.finditer(pattern, text)]
    n = len(hits)
    ok = True
    if expect_min is not None and n < expect_min:
        ok = False
    if expect_max is not None and n > expect_max:
        ok = False
    detail = {"pattern": pattern, "hits": n, "expect_min": expect_min, "expect_max": expect_max}
    if ok:
        return True, detail
    detail["kind"] = FailureKind.SCRIPT_ERROR.value
    for ln in text.splitlines():
        if re.search(pattern, ln):
            detail.setdefault("samples", []).append(ln.strip()[:200])
        if len(detail.get("samples", [])) >= sample:
            break
    return False, detail


# ---------------------------------------------------------------- 状态新鲜度
def assert_state_fresh(state: Dict[str, Any], max_age_minutes: float = 10.0) -> Tuple[bool, Dict[str, Any]]:
    """探针导出的 when 是否够新。过期状态会让判定悄悄失效，这条专门防这个。"""
    import datetime as _dt
    when = (state or {}).get("when")
    if not when:
        return _fail({"error": "state.when 缺失", "kind": FailureKind.SCRIPT_ERROR.value})
    try:
        ts = _dt.datetime.fromisoformat(str(when).replace("Z", "+00:00"))
    except ValueError:
        return _fail({"error": "无法解析 when: %s" % when, "kind": FailureKind.SCRIPT_ERROR.value})
    now = _dt.datetime.now(_dt.timezone.utc)
    age = (now - ts).total_seconds() / 60.0
    detail = {"when": when, "age_minutes": round(age, 2), "max_age_minutes": max_age_minutes}
    if age <= max_age_minutes:
        return True, detail
    detail["kind"] = FailureKind.SCRIPT_ERROR.value
    return False, detail


def classify(passed: bool, details: Dict[str, Any]) -> Optional[FailureKind]:
    if passed:
        return None
    kind = (details or {}).get("kind")
    try:
        return FailureKind(kind) if kind else FailureKind.SCRIPT_ERROR
    except ValueError:
        return FailureKind.SCRIPT_ERROR


# ---------------------------------------------------------------- 用例执行
ASSERT_MAP = {
    "state": assert_state,
    "items_registered": assert_items_registered,
    "class_invariants": assert_class_invariants,
    "log_match": assert_log_match,
    "state_fresh": assert_state_fresh,
    "inv": assert_inv,
    "log_clean": assert_log_clean,
    "tps": assert_tps,
    "gui_slots": assert_gui_slots,
    "script_pass": assert_script_pass,
}


def run_asserts(case: Dict[str, Any], ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    """case['asserts'] = [{"type": "log_clean", "args": {...}}, ...]"""
    out = []
    for spec in case.get("asserts") or []:
        kind = spec.get("type")
        fn = ASSERT_MAP.get(kind)
        if fn is None:
            out.append({"type": kind, "passed": False,
                        "detail": {"error": "unknown assert type", "kind": FailureKind.SCRIPT_ERROR.value}})
            continue
        args = dict(spec.get("args") or {})
        # 注入上下文里能提供的参数
        for k in ("snapshot", "screen", "results"):
            if k in args and isinstance(args[k], str) and args[k].startswith("$"):
                args[k] = ctx.get(args[k][1:], {})
        try:
            ok, detail = fn(**args)
        except TypeError as e:
            ok, detail = False, {"error": "bad args: %s" % e, "kind": FailureKind.SCRIPT_ERROR.value}
        out.append({"type": kind, "passed": bool(ok), "detail": detail})
    return out


if __name__ == "__main__":
    # 现场自检：对本机的 RPG 整合包日志跑一次 log_clean
    import sys
    log = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\kjds\Desktop\.minecraft\versions\RPG奇幻整合包\logs\latest.log"
    ok, detail = assert_log_clean(log, max_hits=0, sample=3)
    print(json.dumps({"passed": ok, "detail": detail}, ensure_ascii=False, indent=1)[:1500])
