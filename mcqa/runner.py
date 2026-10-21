"""mcqa.runner —— 最小可用 QA 运行器

用法：
    python -m mcqa.runner run cases/RPG-LOG-01.json
    python -m mcqa.runner run cases/            # 跑目录
    python -m mcqa.runner run cases/ --out reports/run.json --md

上下文（ctx）来源，按用例里的 `ctx` 字段声明：
    log       从游戏日志读（默认读整合包 logs/latest.log）
    results   KubeJS 内嵌脚本写出的 JSON（kubejs/qa_results/*.json）
    snapshot  外部给的 JSON（背包/坐标等），没有就为空
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import asserts as A

DEFAULT_GAME_DIR = Path(r"C:\Users\kjds\Desktop\.minecraft\versions\RPG奇幻整合包")


def _load_json(p: Path) -> Dict[str, Any]:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"_error": str(e)}



QA_LINE = re.compile(r"\[QA\]\s+(\d+)/(\d+)\s+(.*)$")


def load_state_from_log(log_path: Path) -> Dict[str, Any]:
    """从 latest.log 里还原探针状态：找最后一组完整的 [QA] i/n 分块。"""
    if not log_path.exists():
        return {}
    try:
        text = A._read_text(log_path)
    except Exception:
        return {}
    chunks: Dict[int, str] = {}
    total = 0
    for line in text.splitlines():
        m = QA_LINE.search(line)
        if not m:
            continue
        idx, tot, body = int(m.group(1)), int(m.group(2)), m.group(3)
        # 只保留最后一组：编号变小就重置
        if idx == 1:
            chunks, total = {}, tot
        chunks[idx] = body
        total = tot
    if not chunks or len(chunks) < total:
        return {}
    body = "".join(chunks.get(i, "") for i in range(1, total + 1))
    try:
        return json.loads(body)
    except Exception:
        return {}


def load_state(game_dir: Path) -> Dict[str, Any]:
    """优先读文件（万一以后 class filter 放开），否则从日志还原。"""
    fp = game_dir / "kubejs" / "qa_results" / "latest.json"
    d = _load_json(fp)
    if d:
        return d
    return load_state_from_log(game_dir / "logs" / "latest.log")


def build_ctx(case: Dict[str, Any], game_dir: Path) -> Dict[str, Any]:
    ctx: Dict[str, Any] = {}
    want = case.get("ctx") or {}
    if "log" in want:
        ctx["log"] = str(game_dir / "logs" / "latest.log")
    if "results" in want:
        rd = game_dir / "kubejs" / "qa_results"
        merged: List[Dict[str, Any]] = []
        if rd.exists():
            for f in sorted(rd.glob("*.json")):
                d = _load_json(f)
                merged.extend(d.get("results") or [])
        ctx["results"] = {"results": merged}
    if "state" in want:
        ctx["state"] = load_state(game_dir)
    if "snapshot" in want:
        sp = Path(want["snapshot"])
        ctx["snapshot"] = _load_json(sp)
    return ctx


def resolve_args(spec: Dict[str, Any], ctx: Dict[str, Any], game_dir: Path) -> Dict[str, Any]:
    args = dict(spec.get("args") or {})
    if spec.get("type") in ("log_clean", "log_match") and "log_path" not in args:
        args["log_path"] = ctx.get("log") or str(game_dir / "logs" / "latest.log")
    for k, v in list(args.items()):
        if isinstance(v, str) and v.startswith("$"):
            args[k] = ctx.get(v[1:], {})
    return args


def run_case(case: Dict[str, Any], game_dir: Path) -> Dict[str, Any]:
    ctx = build_ctx(case, game_dir)
    # 依赖游戏内探针的用例：没数据就报 PENDING，不要误判为 FAIL
    req = case.get("requires") or {}
    if req.get("driver"):
        return {"case": case.get("id"), "name": case.get("name"),
                "description": case.get("description", ""), "passed": None,
                "status": "PENDING", "reason": "需要输入驱动层（当前测试对象上不可用，见阻塞记录）",
                "seconds": 0.0, "asserts": [], "failure_kinds": [], "budget": case.get("budget")}
    if req.get("state") and not ctx.get("state"):
        return {"case": case.get("id"), "name": case.get("name"),
                "description": case.get("description", ""), "passed": None,
                "status": "PENDING", "reason": "等待 qa_probe.js 导出 kubejs/qa_results/latest.json",
                "seconds": 0.0, "asserts": [], "failure_kinds": [], "budget": case.get("budget")}
    t0 = time.time()
    results = []
    for spec in case.get("asserts") or []:
        fn = A.ASSERT_MAP.get(spec.get("type"))
        if fn is None:
            results.append({"type": spec.get("type"), "passed": False,
                            "detail": {"error": "unknown assert type"}})
            continue
        args = resolve_args(spec, ctx, game_dir)
        try:
            ok, detail = fn(**args)
        except Exception as e:  # noqa: BLE001
            ok, detail = False, {"error": "%s: %s" % (type(e).__name__, e)}
        results.append({"type": spec.get("type"), "passed": bool(ok), "detail": detail})
    passed = all(r["passed"] for r in results)
    kinds = [A.classify(r["passed"], r["detail"]) for r in results if not r["passed"]]
    return {
        "status": "PASS" if passed else "FAIL",
        "case": case.get("id"),
        "name": case.get("name"),
        "description": case.get("description", ""),
        "passed": passed,
        "seconds": round(time.time() - t0, 2),
        "asserts": results,
        "failure_kinds": [k.value for k in kinds if k],
        "budget": case.get("budget"),
    }


def collect(case_path: Path) -> List[Dict[str, Any]]:
    if case_path.is_dir():
        cases = []
        for f in sorted(case_path.glob("*.json")):
            cases.append(json.loads(f.read_text(encoding="utf-8")))
        return cases
    return [json.loads(case_path.read_text(encoding="utf-8"))]


def diff_runs(prev: Dict[str, Any], cur: Dict[str, Any]) -> List[Dict[str, Any]]:
    """逐条对比两轮结果：新增 / 修复 / 退化 / 仍失败 / 仍通过 / 消失。"""
    def idx(run):
        m = {}
        for r in run.get("results") or []:
            m[r.get("case")] = r
        return m
    a, b = idx(prev), idx(cur)
    out = []
    for case in sorted(set(a) | set(b)):
        pa, pb = a.get(case), b.get(case)
        sa = (pa or {}).get("status") or ("PASS" if (pa or {}).get("passed") else "FAIL")
        sb = (pb or {}).get("status") or ("PASS" if (pb or {}).get("passed") else "FAIL")
        if pa is None:
            change = "NEW"
        elif pb is None:
            change = "REMOVED"
        elif sa == sb:
            change = "STILL_PASS" if sb == "PASS" else ("STILL_FAIL" if sb == "FAIL" else "STILL_" + sb)
        elif sb == "PASS":
            change = "FIXED"
        elif sa == "PASS":
            change = "REGRESSED"
        else:
            change = "CHANGED"
        out.append({"case": case, "prev": sa, "now": sb, "change": change,
                    "kinds_now": (pb or {}).get("failure_kinds") or []})
    return out


def to_markdown(run: Dict[str, Any]) -> str:
    L = ["# QA 运行报告", "", "生成时间：%s" % run["when"], "",
         "| 用例 | 结果 | 失败类 | 说明 |", "|---|---|---|---|"]
    for r in run["results"]:
        L.append("| %s %s | %s | %s | %s |" % (
            r["case"], r["name"] or "",
            r.get("status") or ("PASS" if r["passed"] else "FAIL"),
            ", ".join(r["failure_kinds"]) or "-",
            r["description"][:40]))
    L.append("")
    L.append("合计 **%d/%d** 通过，%d 待定" % (run["passed"], run["total"], run.get("pending", 0)))
    # 未通过用例的细节
    if run.get("diff"):
        s = run["diff"]["summary"]
        L += ["", "## 与上一轮对比（%s）" % run["diff"]["against"], "",
              "| 变化 | 数量 |", "|---|---|",
              "| 新增用例 | %d |" % s["NEW"],
              "| 修复 | %d |" % s["FIXED"],
              "| 退化 | %d |" % s["REGRESSED"],
              "| 仍失败 | %d |" % s["STILL_FAIL"],
              "| 仍通过 | %d |" % s["STILL_PASS"], ""]
        marks = [x for x in run["diff"]["items"] if x["change"] in ("FIXED", "REGRESSED", "CHANGED")]
        if marks:
            L += ["| 用例 | 上一轮 | 本轮 | 变化 |", "|---|---|---|---|"]
            for x in marks:
                L.append("| %s | %s | %s | %s |" % (x["case"], x["prev"], x["now"], x["change"]))
            L.append("")
    fails = [r for r in run["results"] if not r.get("passed")]
    if fails:
        L += ["", "## 失败细节", ""]
        for r in fails:
            L.append("### %s %s" % (r["case"], r["name"] or ""))
            for a in r["asserts"]:
                if a["passed"]:
                    continue
                L.append("- `%s` 失败：`%s`" % (a["type"], json.dumps(a["detail"], ensure_ascii=False)[:600]))
                if a["type"] == "log_clean":
                    c = (a["detail"] or {}).get("counts") or {}
                    L.append("  计数：%s" % c)
                    for s in (a["detail"] or {}).get("samples", [])[:4]:
                        L.append("  - L%s [%s] `%s` %s" % (s["line"], s["level"], s["logger"][:24], s["msg"][:120]))
            L.append("")
    return "\n".join(L)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="mcqa")
    ap.add_argument("cmd", choices=["run"], help="目前只有 run")
    ap.add_argument("path", help="用例文件或目录")
    ap.add_argument("--game-dir", default=str(DEFAULT_GAME_DIR))
    ap.add_argument("--out", default="")
    ap.add_argument("--md", action="store_true", help="同时输出 markdown 报告")
    ap.add_argument("--compare", default="", help="与上一轮报告 JSON 对比，输出逐条变化")
    args = ap.parse_args(argv)

    game_dir = Path(args.game_dir)
    cases = collect(Path(args.path))
    out = {"when": time.strftime("%Y-%m-%dT%H:%M:%S"), "game_dir": str(game_dir), "results": []}
    for c in cases:
        r = run_case(c, game_dir)
        out["results"].append(r)
        tag = r.get("status") or ("PASS" if r["passed"] else "FAIL")
        print("[%s] %-14s %s  %s" % (tag, r["case"], ", ".join(r["failure_kinds"]) or "", r["name"] or ""))
    out["total"] = len(out["results"])
    out["passed"] = sum(1 for r in out["results"] if r.get("passed") is True)
    out["pending"] = sum(1 for r in out["results"] if r.get("passed") is None)

    if args.compare:
        prev = _load_json(Path(args.compare))
        if not prev.get("results"):
            print("!! --compare 文件无效或没有 results：%s" % args.compare)
        else:
            d = diff_runs(prev, out)
            out["diff"] = {"against": args.compare, "items": d,
                           "summary": {k: sum(1 for x in d if x["change"] == k)
                                       for k in ("NEW", "FIXED", "REGRESSED", "STILL_PASS", "STILL_FAIL", "REMOVED", "CHANGED")}}
            s = out["diff"]["summary"]
            print("\n== 与上一轮对比 ==")
            print("  新增 %d / 修复 %d / 退化 %d / 仍失败 %d / 仍通过 %d" % (
                s["NEW"], s["FIXED"], s["REGRESSED"], s["STILL_FAIL"], s["STILL_PASS"]))
            for x in d:
                if x["change"] in ("FIXED", "REGRESSED", "CHANGED"):
                    print("  %-9s %-16s %s -> %s  %s" % (x["change"], x["case"], x["prev"], x["now"],
                                                          ",".join(x["kinds_now"])))

    if args.out:
        op = Path(args.out)
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print("→ %s" % op)
        if args.md:
            mp = op.with_suffix(".md")
            mp.write_text(to_markdown(out), encoding="utf-8")
            print("→ %s" % mp)
    print("\n合计 %d/%d 通过，%d 待定" % (out["passed"], out["total"], out.get("pending", 0)))
    return 0 if out["passed"] + out.get("pending", 0) == out["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
