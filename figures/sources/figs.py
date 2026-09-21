import os, matplotlib
matplotlib.use("Agg")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
os.makedirs(OUT, exist_ok=True)
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "model"))
import model2 as model
from model2 import *

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
SP = spill_times()

STYLE = {
    "CC":      dict(m="s", c="#1f2d5a", s=90),
    "relay":   dict(m="^", c="#3b6fb6", s=80),
    "sensor":  dict(m="o", c="#2a9d8f", s=55),
    "tanker":  dict(m="D", c="#6c757d", s=60),
    "service": dict(m="D", c="#e76f51", s=60),
    "uav":     dict(m="P", c="#8e44ad", s=90),
    "worker":  dict(m="*", c="#d4a017", s=120),
}
LABEL = {"CC": "Control center", "relay": "Shore-based LoRaWAN gateway", "sensor": "Sensor (buoy)",
         "tanker": "Tanker", "service": "Port service vessel", "uav": "UAV",
         "worker": "Port worker (radio + UWB)"}

def snapshot(ax, t, title):
    # зони
    for k, ((x0, x1), (y0, y1)) in ZONES.items():
        fc = {3: "#dbe7f5", 2: "#e9f0f8", 1: "#f6f9fc"}[W[k]]
        ax.add_patch(Rectangle((x0, y0), .5, .5, fc=fc, ec="#9fb3c8", lw=.6))
        if k in SP and SP[k] <= t:
            ax.add_patch(Rectangle((x0, y0), .5, .5, fc="none", ec="#c0392b", hatch="////", lw=0, alpha=.45))
        ax.text(x0 + .04, y1 - .07, f"Z{k}", fontsize=7, color="#4a5b6e")
    ax.add_patch(Rectangle((-.1, -.55), 2.2, .55, fc="#efe9df", ec="none"))   # берег
    ax.text(.3, -.5, "shore", fontsize=7, color="#7a6a55", ha="center")
    ax.add_patch(Rectangle((.8, -.52), .25, .14, fc="none", ec="#7a6a55", lw=.7, ls=":"))
    ax.text(.925, -.34, "assembly point", fontsize=6, color="#7a6a55", ha="center")
    act = [n for n in CONFIGS["C"] if active(n, t)]
    E = edges_at(t, act)
    drawn = set()
    for u, v, _ in E:
        (x1, y1), (x2, y2) = NODES[u]["pos"](t), NODES[v]["pos"](t)
        wired = (u, v) in WIRED or (v, u) in WIRED
        sym = (v, u) in {(a, b) for a, b, _ in E}
        if sym:
            if (v, u) in drawn:
                continue
            drawn.add((u, v))
            ax.plot([x1, x2], [y1, y2], color="#555" if wired else "#8aa1b8",
                    lw=1.4 if wired else .8, ls="-" if wired else "--", zorder=2)
        else:
            d = math.hypot(x2 - x1, y2 - y1) or 1
            ux, uy = (x2 - x1) / d, (y2 - y1) / d
            ax.annotate("", xy=(x2 - ux * .025, y2 - uy * .025), xytext=(x1 + ux * .015, y1 + uy * .015),
                        arrowprops=dict(arrowstyle="-|>", color="#2a9d8f", lw=.8,
                                        linestyle="dotted", mutation_scale=8), zorder=2)
    for n in CONFIGS["C"]:
        ty = NODES[n]["type"]; st = STYLE[ty]
        a, b = NODES[n]["life"]
        if t < a:
            continue
        x, y = NODES[n]["pos"](min(t, b - 1) if t >= b else t)
        if t >= b:
            if n in ("R1", "S1"):   # вузли, що вийшли з ладу
                ax.scatter([x], [y], marker="x", c="#c0392b", s=70, lw=2, zorder=5)
                ax.text(x - .02, y - .13, n, fontsize=7, color="#c0392b", ha="right")
            continue
        ax.scatter([x], [y], marker=st["m"], c=st["c"], s=st["s"], ec="white", lw=.6, zorder=4)
        dx, dy, ha = .05, .04, "left"
        if n == "R1": dx, dy, ha = -.02, -.14, "right"
        if ty == "worker" and y < -.2:
            dx, dy, ha = (-.05, .04, "right") if n == "W1" else (.05, .04, "left")
        ax.text(x + dx, y + dy, n, fontsize=7, color="#222", zorder=6, ha=ha)
    ax.set_xlim(-.1, 2.1); ax.set_ylim(-.55, 1.55); ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, fontsize=9)
    for s in ax.spines.values():
        s.set_color("#bbb")

fig, axs = plt.subplots(1, 3, figsize=(10.5, 4.0))
snapshot(axs[0], 30, "(a) t = 30 min, normal operation")
snapshot(axs[1], 75, "(b) t = 75 min, after the accident, κ(t) = 0.5")
snapshot(axs[2], 105, "(c) t = 105 min, V2 and UAV at the terminal")
handles = [Line2D([], [], marker=STYLE[k]["m"], color="w", markerfacecolor=STYLE[k]["c"],
                  markersize=8 if k != "worker" else 11, label=LABEL[k]) for k in STYLE]
handles += [Line2D([], [], marker="x", color="#c0392b", lw=0, markersize=7, label="Failed node"),
            Line2D([], [], color="#8aa1b8", ls="--", label="Symmetric link"),
            Line2D([], [], color="#2a9d8f", ls=":", label="LoRaWAN uplink"),
            Line2D([], [], color="#555", lw=1.4, label="Wired link"),
            Rectangle((0, 0), 1, 1, fc="none", ec="#c0392b", hatch="////", alpha=.5, label="Polluted zone")]
fig.legend(handles=handles, loc="lower center", ncol=6, fontsize=7.2, frameon=False, bbox_to_anchor=(.5, -.02))
plt.tight_layout(rect=(0, .1, 1, 1))
plt.savefig(OUT + "/fig2_snapshots.png", dpi=600, bbox_inches="tight")

# ---- Рис. 3: O(t) ----
fig, ax = plt.subplots(figsize=(7.2, 3.3))
ax.axvspan(60, 120, color="#f3d9d4", alpha=.6, lw=0)
ax.axvline(60, color="#c0392b", lw=1)
ax.text(62, .93, "accident, link degradation (κ = 0.5)", fontsize=7.5, color="#a93226")
cols = {"A": "#2a9d8f", "B": "#3b6fb6", "C": "#e76f51"}
names = {"A": "A: fixed nodes only", "B": "B: A + vessels", "C": "C: B + workers + UAV"}
for cfg in "ABC":
    O = run(cfg)[0]
    ax.step(TIMES, [O[t] for t in TIMES], where="post", color=cols[cfg], lw=1.6, label=names[cfg])
Os = run_static("C")
ax.step(TIMES, [Os[t] for t in TIMES], where="post", color=cols["C"], lw=1.1, ls=":",
        label="C, time-aggregated static graph")
ax.set_xlim(0, 180); ax.set_ylim(0, 1)
from matplotlib.ticker import FuncFormatter
ax.yaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:.1f}"))
ax.set_xlabel("Time t, min"); ax.set_ylabel("Observability score O(t)")
ax.grid(alpha=.3, lw=.5)
ax.legend(fontsize=7.3, loc="upper left", bbox_to_anchor=(0, .88), frameon=False)
plt.tight_layout()
plt.savefig(OUT + "/fig3_index.png", dpi=600)
print("ok")

