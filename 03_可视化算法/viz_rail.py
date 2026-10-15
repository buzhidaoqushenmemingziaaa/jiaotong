# -*- coding: utf-8 -*-
"""可视化：列车在线路上跑 + 客流。

产出：
    viz_out/fig_stringline.png   运行图（时空图）—— 每列车一条斜线
    viz_out/fig_trains.gif       动画：列车沿线路移动 + 断面客流/满载率
    viz_out/fig_flow.png         客流 vs 运力（静态四联图）
    viz_out/fig_crowd.gif        动画：断面满载率热力演进

用法:
    python viz_rail.py --config handover/line14.json --peak morning
"""

from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.patches import Rectangle

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

from run_v11 import Case, solve          # noqa: E402
import od_demand                          # noqa: E402

OUT = "viz_out"
os.makedirs(OUT, exist_ok=True)


# --------------------------------------------------------------------------
# 列车轨迹重构
# --------------------------------------------------------------------------


def route_profile(case, r):
    """交路 r 的单程「站序 → 累计里程 / 累计时刻」表。

    返回 (station_idx, cum_km, cum_min)：长度 = 该交路站数。
    """
    L = case.cfg["line"]
    o, t = r["origin"] - 1, r["terminus"] - 1
    st = list(range(o, t + 1))
    cum_km, cum_min = [0.0], [0.0]
    for i in range(1, len(st)):
        m = st[i - 1]
        cum_km.append(cum_km[-1] + L["section_length_km"][m])
        cum_min.append(cum_min[-1] + L["run_time_min"][m]
                       + L["dwell_time_s"][st[i]] / 60.0)
    return st, cum_km, cum_min


def reconstruct(case, res, fine=0.25):
    """由聚合的 a(t) 还原每一趟车的始发时刻。"""
    dt = case.dt
    grid = np.arange(0.0, case.T * dt + fine, fine)
    trains = {}
    for ri, r in enumerate(case.routes):
        rid = r["id"]
        if rid not in res["rid"]:
            continue
        col = res["rid"].index(rid)
        Tr = case.Tcyc[rid]
        # λ(τ) = a(τ)/T_r  （列/min）
        a_series = np.array(res["a"], dtype=float)[:, col]
        idx = np.clip((grid / dt).astype(int), 0, case.T - 1)
        lam = a_series[idx] / Tr
        cum = np.concatenate([[0.0], np.cumsum(0.5 * (lam[1:] + lam[:-1])
                                               * np.diff(grid))])
        n_max = int(cum[-1])
        deps = []
        for n in range(1, n_max + 1):
            j = int(np.searchsorted(cum, n))
            if j >= len(grid):
                break
            deps.append(float(grid[j]))
        # 每趟车跑「单程去 + 单程回」，再交给下一趟
        st, ckm, cmin = route_profile(case, r)
        one_way = cmin[-1]
        trains[rid] = {"deps": deps, "one_way": one_way, "Tr": Tr,
                       "st": st, "ckm": ckm, "cmin": cmin,
                       "len": ckm[-1], "color": None}
    return grid, trains


def train_positions(tr, tau):
    """返回该时刻所有在途列车的 (里程位置, 方向)。

    ★ 每趟车只跑**一个往返**（[t_d, t_d + T_r]），跑完就交给下一趟——
    因此任一时刻的在途车数 = 「过去 T_r 分钟内发车次数」，
    这正是 a(t) 的物理含义。**不能让它无限循环**，否则在途数会虚高。
    """
    out = []
    for td in tr["deps"]:
        ph = tau - td
        if ph < 0 or ph >= tr["Tr"]:
            continue
        if ph <= tr["one_way"]:
            k = float(np.interp(ph, tr["cmin"], tr["ckm"]))
            out.append((k, +1))
        else:
            ph2 = ph - tr["one_way"]
            if ph2 > tr["one_way"]:
                continue
            k = float(np.interp(ph2, tr["cmin"], tr["ckm"]))
            out.append((tr["len"] - k, -1))
    return out


# --------------------------------------------------------------------------
# 图 1：运行图（时空图）
# --------------------------------------------------------------------------


def fig_stringline(case, res, grid, trains, path=None):
    fig, ax = plt.subplots(figsize=(11, 6.2))
    colors = {"r0": "#1f77b4", "r1": "#d62728", "r2": "#2ca02c"}
    cum = np.concatenate([[0.0], np.cumsum(case.cfg["line"]["section_length_km"])])
    ymax = cum[-1]
    for rid, tr in trains.items():
        for td in tr["deps"]:
            xs, ys = [], []
            for (a, b) in ((0.0, tr["one_way"]), (tr["one_way"], 2 * tr["one_way"])):
                ph = np.linspace(a, b, 40)
                k = np.interp(ph, tr["cmin"], tr["ckm"])
                if a > 0:
                    k = tr["len"] - k
                xs.append(td + ph)
                ys.append(k)
            ax.plot(np.concatenate(xs), np.concatenate(ys),
                    color=colors.get(rid, "gray"), lw=0.9, alpha=0.85)
    for s, name in enumerate(case.cfg["line"]["stations"]):
        ax.axhline(cum[s], color="0.88", lw=0.5, zorder=0)
    ax.set_xlim(0, case.T * case.dt)
    ax.set_ylim(-1, ymax + 1)
    ax.set_yticks([cum[i] for i in range(0, len(cum), 2)])
    ax.set_yticklabels([case.cfg["line"]["stations"][i]
                        for i in range(0, len(cum), 2)], fontsize=8)
    ticks = range(0, case.T * case.dt + 1, 60)
    ax.set_xticks(list(ticks))
    ax.set_xticklabels([f"{6 + int(t // 60):02d}:{int(t % 60):02d}" for t in ticks],
                       fontsize=8)
    ax.set_xlabel("时刻")
    ax.set_ylabel("里程（按车站）")
    ax.set_title("列车运行图（时空图）——每条斜线是一列车在跑", fontsize=12)
    hs = [plt.Line2D([], [], color=colors[r["id"]], lw=2, label=r["name"])
          for r in case.routes if r["id"] in trains]
    ax.legend(handles=hs, loc="upper left", fontsize=9)
    ax.grid(axis="x", ls=":", alpha=0.35)
    fig.tight_layout()
    p = path or f"{OUT}/fig_stringline.png"
    fig.savefig(p, dpi=140)
    plt.close(fig)
    return p


# --------------------------------------------------------------------------
# 图 2：动画 —— 列车在线路上跑 + 断面客流
# --------------------------------------------------------------------------


def fig_trains_gif(case, res, grid, trains, path=None, fps=10, stride=4):
    L = case.cfg["line"]
    cum = np.concatenate([[0.0], np.cumsum(L["section_length_km"])])
    total_km = cum[-1]
    colors = {"r0": "#1f77b4", "r1": "#d62728", "r2": "#2ca02c"}
    lanes = {r["id"]: i for i, r in enumerate(case.routes) if r["id"] in trains}
    n_lane = len(lanes)

    frames = list(range(0, case.T * case.dt + 1, max(1, int(case.dt / 2))))
    fig = plt.figure(figsize=(11.5, 6.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.15, 1.0], hspace=0.42)
    ax = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    def draw(i):
        tau = frames[i]
        ax.clear()
        ax2.clear()
        # ---- 上：线路 + 列车 ----
        ax.plot([0, total_km], [0, 0], color="0.35", lw=2.2, zorder=1)
        for s in range(len(cum)):
            ax.plot([cum[s]], [0], "o", color="0.35", ms=4, zorder=3)
            ax.text(cum[s], -0.32 - 0.30 * (s % 2),
                    L["stations"][s], ha="center", va="top", fontsize=6.5,
                    rotation=45 if len(cum) > 14 else 0)
        for rid, ln in lanes.items():
            ax.plot([0, trains[rid]["len"]], [0.55 + 0.42 * ln] * 2,
                    color=colors[rid], lw=1.0, alpha=0.25)
        for rid, ln in lanes.items():
            y = 0.55 + 0.42 * ln
            for k, d in train_positions(trains[rid], tau):
                ax.add_patch(Rectangle((k - total_km * 0.006, y - 0.11),
                                       total_km * 0.012, 0.22,
                                       color=colors[rid], zorder=4))
        ax.set_xlim(-total_km * 0.03, total_km * 1.03)
        ax.set_ylim(-1.15, 0.55 + 0.42 * max(1, n_lane - 1) + 0.45)
        ax.set_yticks([0.55 + 0.42 * i for i in range(n_lane)])
        ax.set_yticklabels([case.cfg["routings"][i]["name"] for i in
                            [list(case.R).index(x) for x in lanes]], fontsize=8)
        ax.set_xticks([])
        ax.set_title(f"列车在线路上运行　　时刻 {6 + tau // 60:02d}:{tau % 60:02d}"
                     f"　｜　在线 {int(res['atot'][min(int(tau // case.dt), case.T - 1)])} 列",
                     fontsize=12)
        hs = [plt.Line2D([], [], color=colors[r], lw=6, label=case.cfg["routings"][
            list(case.R).index(r)]["name"]) for r in lanes]
        ax.legend(handles=hs, loc="upper right", fontsize=8, ncol=n_lane, frameon=False)
        ax.axis("off")
        ax.add_patch(Rectangle((0, 0), 0.001, 0.001, alpha=0))   # 保持 axes

        # ---- 下：断面客流 vs 运力 ----
        t = min(int(tau // case.dt), case.T - 1)
        m = np.arange(1, case.M + 1)
        q = np.array(case.q_hat[t])
        F = np.array(res["F"][t])
        cap = case.rho2 * case.C * F
        xkm = (cum[:-1] + cum[1:]) / 2
        ax2.bar(xkm, q, width=total_km / case.M * 0.72,
                color="#9ecae1", edgecolor="#4292c6", lw=0.6, label="断面客流")
        ax2.plot(xkm, cap, color="#d62728", lw=2.0, marker="o", ms=3,
                 label="运力上限 ρ₂·C·F")
        over = q > cap
        if over.any():
            ax2.bar(xkm[over], q[over], width=total_km / case.M * 0.72,
                    color="#fc9272", edgecolor="#cb181d", lw=0.6, zorder=3)
        ax2.set_xlim(-total_km * 0.03, total_km * 1.03)
        ax2.set_ylim(0, max(q.max(), (res["F"][t].__len__() and cap.max())) * 1.30)
        ax2.set_ylabel("人/h", fontsize=9)
        ax2.set_xlabel("里程（km）", fontsize=9)
        ax2.tick_params(labelsize=8)
        ax2.legend(fontsize=8, loc="upper right", frameon=False)
        ax2.set_title(f"断面客流 vs 运力　　共线段列车流 {res['F'][t][0]:.1f} 列/h",
                      fontsize=10)

    def upd(i):
        draw(i)
        return []

    fig.subplots_adjust(left=0.07, right=0.98, top=0.92, bottom=0.09)
    ani = FuncAnimation(fig, upd, frames=len(frames), interval=1000 / fps, blit=False)
    p = path or f"{OUT}/fig_trains.gif"
    ani.save(p, writer=PillowWriter(fps=fps))
    plt.close(fig)
    return p


# --------------------------------------------------------------------------
# 图 3：客流 vs 运力（静态四联图）
# --------------------------------------------------------------------------


def fig_flow(case, res, path=None):
    L = case.cfg["line"]
    cum = np.concatenate([[0.0], np.cumsum(L["section_length_km"])])
    xkm = (cum[:-1] + cum[1:]) / 2
    total = cum[-1]
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.2))

    ax = axes[0][0]
    T = case.T
    qsm = np.array(case.q_hat)
    for m in range(0, case.M, 2):
        ax.plot(range(T), qsm[:, m], lw=1.2, label=f"区段{m + 1}")
    ax.set_title("断面客流随时段演进", fontsize=11)
    ax.set_xlabel("决策步")
    ax.set_ylabel("人/h")
    ax.legend(fontsize=6.5, ncol=2, frameon=False)
    ax.grid(ls=":", alpha=0.35)

    ax = axes[0][1]
    Fm = np.array(res["F"])
    im = ax.imshow(Fm.T, aspect="auto", origin="lower", cmap="YlOrRd")
    ax.set_title("区段列车流 F(t,m)（列/h）", fontsize=11)
    ax.set_xlabel("决策步")
    ax.set_ylabel("区段")
    fig.colorbar(im, ax=ax, fraction=0.046)

    ax = axes[1][0]
    tpk = int(np.argmax([sum(r) for r in case.q_hat]))
    q = np.array(case.q_hat[tpk])
    cap = case.rho2 * case.C * np.array(res["F"][tpk])
    ax.bar(xkm, q, width=total / case.M * 0.72, color="#9ecae1",
           edgecolor="#4292c6", lw=0.6, label="客流")
    ax.plot(xkm, cap, color="#d62728", lw=2, marker="o", ms=3, label="运力上限")
    ov = q > cap
    if ov.any():
        ax.bar(xkm[ov], q[ov], width=total / case.M * 0.72, color="#fc9272",
               edgecolor="#cb181d", lw=0.6, zorder=3, label="超出运力")
    ax.set_title(f"峰值步 t={tpk + 1} 的断面客流 vs 运力", fontsize=11)
    ax.set_xlabel("里程（km）")
    ax.set_ylabel("人/h")
    ax.legend(fontsize=8, frameon=False)
    ax.grid(ls=":", alpha=0.35)

    ax = axes[1][1]
    at = res["atot"]
    ax.step(range(T), at, where="mid", color="#08519c", lw=2, label="在线车底")
    ax.bar(range(T), [sum(v) for v in zip(*res["x"].values())], color="#6baed6",
           alpha=0.65, label="唤醒")
    ax.bar(range(T), [-sum(v) for v in zip(*res["s"].values())], color="#fd8d3c",
           alpha=0.65, label="回段")
    ax.axhline(case.n_avail, color="0.4", ls="--", lw=1, label=f"配属 {case.n_avail}")
    ax.set_title("车底运用：在线 / 唤醒 / 回段", fontsize=11)
    ax.set_xlabel("决策步")
    ax.set_ylabel("列")
    ax.legend(fontsize=8, frameon=False)
    ax.grid(ls=":", alpha=0.35)

    fig.suptitle(f"{case.cfg['meta']['line_name']}　{case.peak}峰　"
                 f"｜　峰值在线 {max(at)} 列　｜　共线段流 "
                 f"{max(r[0] for r in res['F']):.1f} 列/h", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    p = path or f"{OUT}/fig_flow.png"
    fig.savefig(p, dpi=140)
    plt.close(fig)
    return p


# --------------------------------------------------------------------------
# 图 4：满载率热力动画
# --------------------------------------------------------------------------


def fig_crowd_gif(case, res, path=None, fps=6):
    L = case.cfg["line"]
    cum = np.concatenate([[0.0], np.cumsum(L["section_length_km"])])
    xkm = (cum[:-1] + cum[1:]) / 2
    total = cum[-1]
    T = case.T
    q = np.array(case.q_hat)
    F = np.array(res["F"])
    load = q / np.maximum(case.C * F, 1e-9)      # 满载率 = 客流 / (定员 × 列车流)

    fig, ax = plt.subplots(figsize=(11.5, 3.6))

    def draw(t):
        ax.clear()
        v = np.clip(load[t], 0, 2.2)
        cols = plt.cm.RdYlGn_r((v - 0.2) / 2.0)
        ax.bar(xkm, np.ones(case.M), width=total / case.M * 0.95, color=cols)
        for m in range(case.M):
            ax.text(xkm[m], 1.06, f"{load[t][m]:.2f}", ha="center", fontsize=6.5)
        ax.axhline(1.0, color="k", lw=1, ls="--")
        ax.axhline(1.394, color="#7f0000", lw=1, ls=":")
        ax.text(total * 0.005, 1.02, "定员 1.00", fontsize=7.5)
        ax.text(total * 0.005, 1.415, "最大载客 1.394", fontsize=7.5, color="#7f0000")
        ax.set_xlim(-total * 0.02, total * 1.02)
        ax.set_ylim(0, 1.62)
        ax.set_yticks([])
        ax.set_xticks([cum[i] for i in range(0, len(cum), 2)])
        ax.set_xticklabels([L["stations"][i] for i in range(0, len(cum), 2)],
                           fontsize=7.5)
        ax.set_title(f"各断面满载率　　时刻 {6 + int(t * case.dt) // 60:02d}:"
                     f"{int(t * case.dt) % 60:02d}　　"
                     f"峰值满载率 {load[t].max():.2f}", fontsize=12)
        ax.set_xlabel("里程（按车站）", fontsize=9)

    fig.subplots_adjust(left=0.03, right=0.98, top=0.84, bottom=0.18)
    ani = FuncAnimation(fig, draw, frames=T, interval=1000 / fps, blit=False)
    p = path or f"{OUT}/fig_crowd.gif"
    ani.save(p, writer=PillowWriter(fps=fps))
    plt.close(fig)
    return p


# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="handover/line14.json")
    ap.add_argument("--peak", default="morning")
    ap.add_argument("--tau", type=int, default=1)
    ap.add_argument("--time-limit", type=float, default=180)
    ap.add_argument("--skip-gif", action="store_true")
    a = ap.parse_args()

    cfg = json.load(io.open(a.config, encoding="utf-8"))
    case = Case(cfg, a.peak)
    global OUT
    OUT = f"viz_out/{a.peak}"
    os.makedirs(OUT, exist_ok=True)
    print(f"求解中… {case.cfg['meta']['line_name']} {a.peak} τ={a.tau}")
    res = solve(case, time_limit=a.time_limit, taus=a.tau)
    print(f"  状态={res['status']}  目标值={res['objective']:.5f}  "
          f"峰值在线={max(res['atot'])}")

    grid, trains = reconstruct(case, res)
    print(f"  重构列车：{ {k: len(v['deps']) for k, v in trains.items()} } 列")

    p1 = fig_stringline(case, res, grid, trains)
    print("  写出", p1)
    p3 = fig_flow(case, res)
    print("  写出", p3)
    if not a.skip_gif:
        p2 = fig_trains_gif(case, res, grid, trains)
        print("  写出", p2)
        p4 = fig_crowd_gif(case, res)
        print("  写出", p4)


if __name__ == "__main__":
    main()
