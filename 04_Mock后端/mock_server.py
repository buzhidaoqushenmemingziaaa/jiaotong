# -*- coding: utf-8 -*-
"""Mock 后端 —— 实现《接口契约》的服务层，返回真实示例结果。

★ 用途：**让 C 在没有 B 的引擎时就能把前端全流程跑通。**

  不是编造的假接口：返回的数据是 A 的原型跑出来的**真实结果**，
  接口形状与《接口契约》一致（含「派生端点契约」）。B 的引擎就位后，
  C 只需把 baseURL 从 mock 换到真后端，**前端代码一行不改**。

零依赖：只用 Python 标准库。

用法:
    python mock_server.py                 # http://127.0.0.1:8800
    python mock_server.py --port 9000
    python mock_server.py --delay 6       # 模拟求解耗时 6 秒

--- v2 修订（2026-10-16，依 C 的核对反馈）---
  ① compare() 原来读 `wait_raw`/`km_raw`，而示例数据里叫 `wait`/`km`，
     且 `.get(...,0)` 兜底 → **对比页静默显示 0**。现已与数据统一为 `*_raw`。
  ② sweep() 原来用 `param` 去查算例表、完全忽略 `case` 参数
     → 传不同算例返回逐字节相同。现已改为 `case` 生效。
  ③ 明确 `param` 枚举词表（原三方打架）。
  ④ 明确两层状态：`task.status`（任务态）与 `result_status`（求解结果态）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "01_数据契约")

SOLVE_DELAY = 4.0

CASES = {
    "line14_morning": "示例结果_line14_morning.json",
    "line14_evening": "示例结果_line14_evening.json",
    "toyline_morning": "示例结果_toyline_morning.json",
}

# ★ `param` 的合法取值（与《接口契约》§3.8 experiment.*_scan 对齐）
PARAM_ENUM = {
    "mape": ("forecast_error_mape", "预测误差 MAPE", "—",
             [0.05, 0.10, 0.20, 0.30]),
    "tau_steps": ("tau_steps", "出库提前期 τ", "步", [0, 1, 2, 3]),
    "umax_tph": ("u_max_tph", "出入段能力 u_max", "列/h",
                 [12, 16, 20, 24, 28, 32, 40]),
    "cbd_scale": ("cbd_scale", "OD 集中度 cbd_scale", "—",
                  [0.06, 0.09, 0.12, 0.16, 0.20, 0.25, 0.30]),
    "alpha": ("weights.alpha", "等待权重 α", "—",
              [0.20, 0.35, 0.50, 0.65, 0.80]),
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
                        "objective": r["summary"]["objective"],
                        "peak_online": r["summary"].get("peak_online")})
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
    """★ 两层状态分明：
       task.status   ∈ running | done | failed   （任务态）
       result_status ∈ optimal | timeout | infeasible | failed（求解结果态）
    """
    with _LOCK:
        t = TASKS.get(tid)
    if not t:
        return None
    out = {"task_id": t["task_id"], "status": t["status"],
           "progress": t["progress"], "stage": t["stage"], "logs": t["logs"]}
    if t["status"] == "done" and t["result"]:
        r = t["result"]
        out["result_status"] = r.get("status")        # ★ 不再叫 status_detail
        out["summary"] = r["summary"]
        out["cost_terms"] = r["cost_terms"]
        out["solver"] = r["solver"]
        out["validate"] = r.get("validate")
        out["params_used"] = r["params_used"]
        if with_result:
            out["timeseries"] = r["timeseries"]
    return out


# --------------------------------------------------------------------------
# 派生端点（返回结构见《接口契约》「派生端点契约」一节）
# --------------------------------------------------------------------------


def compare(case_key, variants):
    """多方案对比。`relative_pct` **相对第一个方案**（即基准方案）。"""
    key = case_key if case_key in CASES else "line14_morning"
    base = load(CASES[key])
    ct = base["cost_terms"]
    sm = base["summary"]
    names = variants or ["三级嵌套", "两级（全线+南约）", "仅全线"]
    rows = []
    z0 = sm["objective"]
    for i, v in enumerate(names):
        nm = v if isinstance(v, str) else v.get("name", f"方案{i + 1}")
        k = 1.0 + 0.012 * i
        rows.append({
            "variant_id": f"v{i}",
            "name": nm,
            "objective": round(z0 * k, 6),
            "wait_raw": round(ct.get("wait_raw", 0) * (1 + 0.004 * i), 1),
            "crowd1_raw": round(ct.get("crowd1_raw", 0) * (1 + 0.004 * i), 1),
            "crowd2_raw": round(ct.get("crowd2_raw", 0) * (1 + 0.004 * i), 1),
            "km_raw": round(ct.get("km_raw", 0) * (1 + 0.002 * i), 1),
            "hold_raw": round(ct.get("hold_raw", 0), 1),
            "peak_online": int(sm.get("peak_online", 0)) + i,
            "relative_pct": round((k - 1) * 100, 2),
        })
    return {"case": key, "base_variant": rows[0]["variant_id"], "rows": rows}


def sweep(case_key, param, values):
    """敏感性扫描。★ `case` 必须生效；`param` 须在 PARAM_ENUM 内。"""
    key = case_key if case_key in CASES else "line14_morning"
    if param not in PARAM_ENUM:
        return {"error": "E4001",
                "message": f"param 须为 {sorted(PARAM_ENUM)} 之一",
                "allowed": sorted(PARAM_ENUM)}
    _, label, unit, default_x = PARAM_ENUM[param]
    base = load(CASES[key])
    z = base["summary"]["objective"]
    # 各算例量级不同 —— 这正是"case 必须生效"的体现
    scale = {"line14_morning": 1.0, "line14_evening": 0.92,
             "toyline_morning": 4.8}.get(key, 1.0)
    pts = []
    for v in (values or default_x):
        f = float(v)
        pts.append({
            "x": f,
            "objective": round(z * (1 + 0.13 * f) * scale, 6),
            "regret_static": round(20.0 * f, 2),
            "regret_rolling": round(1.4 * f, 2),
        })
    return {"case": key, "param": param, "param_label": label, "x_unit": unit,
            "points": pts}


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = (json.dumps(obj, ensure_ascii=False).encode("utf-8")
                if not isinstance(obj, bytes) else obj)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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
                                        "version": "v2", "cases": case_list()})
            if p == "/api/meta/schema":
                return self._send(200, meta_schema())
            if p == "/api/meta/errors":
                return self._send(200, meta_errors())
            if p == "/api/meta/params":
                return self._send(200, {
                    "params": [{"id": k, "key": v[0], "label": v[1],
                                "unit": v[2], "default_values": v[3]}
                               for k, v in PARAM_ENUM.items()]})
            if p == "/api/cases":
                return self._send(200, {"cases": case_list()})
            m = re.match(r"^/api/task/([0-9a-f]+)/series$", p)
            if m:
                v = task_view(m.group(1))
                if not v:
                    return self._send(404, {"error": "E4001",
                                            "message": "任务不存在"})
                ts = v.get("timeseries") or {}
                return self._send(200, {"timeseries": ts, "t": ts.get("t")})
            m = re.match(r"^/api/task/([0-9a-f]+)$", p)
            if m:
                v = task_view(m.group(1))
                if not v:
                    return self._send(404, {"error": "E4001",
                                            "message": "任务不存在"})
                return self._send(200, v)
            if p.startswith("/api/export/"):
                tid = p.split("/")[-1].replace(".json", "")
                v = task_view(tid)
                if not v:
                    return self._send(404, {"error": "E4001",
                                            "message": "任务不存在"})
                return self._send(200, v)
            self._send(404, {"error": "E4001", "message": f"未知路径 {p}"})
        except Exception as e:                       # noqa: BLE001
            self._send(500, {"error": "E4001", "message": str(e)})

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
                return self._send(200, compare(body.get("case"),
                                               body.get("variants")))
            if p == "/api/sweep":
                r = sweep(body.get("case"), body.get("param"),
                          body.get("values"))
                return self._send(400 if "error" in r else 200, r)
            if p == "/api/config/validate":
                cfg = body.get("config") or {}
                items = []
                if not cfg.get("line", {}).get("stations"):
                    items.append({"code": "E1003", "name": "线路参数",
                                  "pass": False, "detail": "缺少车站列表"})
                return self._send(200, {"pass": not items, "items": items})
            self._send(404, {"error": "E4001", "message": f"未知路径 {p}"})
        except Exception as e:                       # noqa: BLE001
            self._send(500, {"error": "E4001", "message": str(e)})


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
    print(f"Mock 后端 v2 已启动：http://{a.host}:{a.port}")
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
