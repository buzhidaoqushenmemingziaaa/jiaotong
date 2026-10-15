# -*- coding: utf-8 -*-
"""Mock 后端 —— 实现《接口契约》的服务层，返回真实示例结果。

★ 用途：**让 C 在没有 B 的引擎时就能把前端全流程跑通。**

  它不是编造的假接口：返回的数据是 A 的原型跑出来的**真实结果**，
  接口形状与《接口契约》一致。B 的引擎就位后，C 只需把 baseURL
  从 mock 换到真后端，**前端代码一行不改**。

零依赖：只用 Python 标准库（不需要 FastAPI / Flask）。

用法:
    python mock_server.py                 # 默认 http://127.0.0.1:8800
    python mock_server.py --port 9000
    python mock_server.py --delay 6       # 模拟求解耗时 6 秒

然后在浏览器或前端里访问 http://127.0.0.1:8800/api/health 自检。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "01_数据契约")

# 求解模拟耗时（秒）——按"真实求解是慢的"设计，逼前端走异步
SOLVE_DELAY = 4.0

CASES = {
    "line14_morning": "示例结果_line14_morning.json",
    "line14_evening": "示例结果_line14_evening.json",
    "toyline_morning": "示例结果_toyline_morning.json",
}

_cache: dict = {}
TASKS: dict = {}
_LOCK = threading.Lock()


def load(name):
    if name not in _cache:
        p = os.path.join(DATA, name)
        if not os.path.exists(p):
            p = os.path.join(HERE, name)
        _cache[name] = json.load(open(p, encoding="utf-8"))
    return _cache[name]


def meta_schema():
    return load("示例_describe_config.json")


def meta_errors():
    return load("示例_describe_errors.json")


def case_list():
    out = []
    for k, f in CASES.items():
        try:
            r = load(f)
            out.append({"id": k, "case_id": r.get("case_id"),
                        "peak": r.get("peak"),
                        "steps": len(r["timeseries"]["t"]),
                        "objective": r["summary"]["objective"]})
        except Exception:
            pass
    return out


# --------------------------------------------------------------------------
# 异步任务
# --------------------------------------------------------------------------


def _run_task(task_id, case_key, time_limit):
    r = load(CASES.get(case_key, CASES["line14_morning"]))
    total = max(0.5, min(SOLVE_DELAY, time_limit or SOLVE_DELAY))
    stages = ["读取配置", "校验参数", "构建模型", "求解中", "整理结果"]
    for i, st in enumerate(stages):
        time.sleep(total / len(stages))
        with _LOCK:
            TASKS[task_id]["progress"] = round((i + 1) / len(stages), 3)
            TASKS[task_id]["stage"] = st
            TASKS[task_id]["logs"].append(f"[{time.strftime('%H:%M:%S')}] {st}")
    with _LOCK:
        TASKS[task_id].update(status="done", progress=1.0, stage="完成",
                              result=r)


def submit(case_key, peak=None, time_limit=None):
    tid = uuid.uuid4().hex[:12]
    with _LOCK:
        TASKS[tid] = {"task_id": tid, "status": "running", "progress": 0.0,
                      "stage": "排队", "logs": [], "result": None,
                      "case": case_key, "peak": peak}
    threading.Thread(target=_run_task, args=(tid, case_key, time_limit),
                     daemon=True).start()
    return tid


def task_view(tid, with_result=True):
    with _LOCK:
        t = TASKS.get(tid)
    if not t:
        return None
    out = {"task_id": t["task_id"], "status": t["status"],
           "progress": t["progress"], "stage": t["stage"], "logs": t["logs"]}
    if t["status"] == "done" and t["result"]:
        r = t["result"]
        out["summary"] = r["summary"]
        out["cost_terms"] = r["cost_terms"]
        out["solver"] = r["solver"]
        out["params_used"] = r["params_used"]
        out["status_detail"] = r["status"]
        if with_result:
            out["timeseries"] = r["timeseries"]
    return out


# --------------------------------------------------------------------------
# 对比 / 灵敏度（由真实结果派生，保证量级真实）
# --------------------------------------------------------------------------


def compare(base_case, variants):
    base = load(CASES.get(base_case, CASES["line14_morning"]))
    out = []
    for i, v in enumerate(variants or ["三级嵌套", "两级（全线+南约）", "仅全线"]):
        k = 1.0 + 0.012 * i
        out.append({
            "name": v if isinstance(v, str) else v.get("name", f"方案{i + 1}"),
            "objective": round(base["summary"]["objective"] * k, 6),
            "wait": round(base["cost_terms"].get("wait_raw", 0) * (1 + 0.004 * i), 1),
            "km": round(base["cost_terms"].get("km_raw", 0) * (1 + 0.002 * i), 1),
            "peak_online": max(base["timeseries"]["a_total"]) + i,
            "relative_pct": round((k - 1) * 100, 2),
        })
    return {"base": base_case, "rows": out}


def sweep(base_case, param, values):
    base = load(CASES.get(param or "line14_morning", CASES["line14_morning"]))
    z = base["summary"]["objective"]
    pts = []
    for v in (values or [0.05, 0.1, 0.2, 0.3]):
        pts.append({"x": v,
                    "objective": round(z * (1 + 0.13 * float(v)), 6),
                    "regret_static": round(20.0 * float(v), 2),
                    "regret_rolling": round(1.4 * float(v), 2)})
    return {"param": param or "mape", "points": pts}


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj, ctype="application/json; charset=utf-8"):
        body = (json.dumps(obj, ensure_ascii=False).encode("utf-8")
                if not isinstance(obj, bytes) else obj)
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_GET(self):
        p = self.path.split("?")[0].rstrip("/")
        try:
            if p in ("/api/health", ""):
                return self._send(200, {"ok": True, "mock": True,
                                        "cases": case_list()})
            if p == "/api/meta/schema":
                return self._send(200, meta_schema())
            if p == "/api/meta/errors":
                return self._send(200, meta_errors())
            if p == "/api/cases":
                return self._send(200, {"cases": case_list()})
            m = re.match(r"^/api/task/([0-9a-f]+)/series$", p)
            if m:
                v = task_view(m.group(1))
                if not v:
                    return self._send(404, {"error": "E_TASK_NOT_FOUND"})
                return self._send(200, {"timeseries": v.get("timeseries"),
                                        "t": (v.get("timeseries") or {}).get("t")})
            m = re.match(r"^/api/task/([0-9a-f]+)$", p)
            if m:
                v = task_view(m.group(1))
                if not v:
                    return self._send(404, {"error": "E_TASK_NOT_FOUND"})
                return self._send(200, v)
            if p.startswith("/api/export/"):
                tid = p.split("/")[-1].replace(".json", "")
                v = task_view(tid)
                if not v:
                    return self._send(404, {"error": "E_TASK_NOT_FOUND"})
                return self._send(200, v)
            self._send(404, {"error": "E_NOT_FOUND", "path": p})
        except Exception as e:                       # noqa: BLE001
            self._send(500, {"error": "E_INTERNAL", "detail": str(e)})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8") if n else "{}"
        try:
            body = json.loads(raw or "{}")
        except Exception:
            body = {}
        p = self.path.split("?")[0].rstrip("/")
        try:
            if p == "/api/solve":
                ck = body.get("case") or body.get("case_id") or "line14_morning"
                if ck not in CASES:
                    ck = "line14_morning"
                tid = submit(ck, body.get("peak"), body.get("time_limit_s"))
                return self._send(200, {"task_id": tid, "status": "running"})
            if p == "/api/compare":
                return self._send(200, compare(body.get("case"), body.get("variants")))
            if p == "/api/sweep":
                return self._send(200, sweep(body.get("case"), body.get("param"),
                                             body.get("values")))
            if p == "/api/config/validate":
                cfg = body.get("config") or {}
                items = []
                if not cfg.get("line", {}).get("stations"):
                    items.append({"field": "line.stations",
                                  "code": "E_CONFIG_MISSING",
                                  "message": "缺少车站列表"})
                return self._send(200, {"pass": not items, "items": items})
            self._send(404, {"error": "E_NOT_FOUND", "path": p})
        except Exception as e:                       # noqa: BLE001
            self._send(500, {"error": "E_INTERNAL", "detail": str(e)})


def main():
    global SOLVE_DELAY
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--delay", type=float, default=4.0,
                    help="模拟求解耗时（秒），用于逼前端走异步")
    a = ap.parse_args()
    SOLVE_DELAY = a.delay
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"Mock 后端已启动：http://{a.host}:{a.port}")
    print(f"  模拟求解耗时 {SOLVE_DELAY}s（前端应按异步设计）")
    print("  自检：GET /api/health")
    print("  可用算例：" + "、".join(CASES))
    print("  Ctrl+C 停止")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
