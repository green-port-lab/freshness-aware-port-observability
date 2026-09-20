"""Figures for the computational evaluation (sensitivity, scalability, criticality, ablation)."""
import csv, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "model"))
RES = os.path.join(HERE, "..", "..", "results")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
COL = {"A": "#2a9d8f", "B": "#3b6fb6", "C": "#e76f51"}
NAVY, GREY = "#1f2d5a", "#8aa1b8"
comma = FuncFormatter(lambda v, p: f"{v:.1f}".replace(".", ","))

def load(name):
    with open(os.path.join(RES, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))

def num(s):
    return float(str(s).replace(",", "."))

# ---------------- чутливість ----------------
rows = load("sensitivity_effects.csv")
groups = {}
for r in rows:
    groups.setdefault(r["parameter"], []).append(r)
titles = {"admissible age scale": "а) масштаб допустимого віку даних",
          "kappa": "б) коефіцієнт погіршення умов зв’язку κ",
          "worker reliability": "в) достовірність спостережень працівника"}
fig, axs = plt.subplots(1, 3, figsize=(10.5, 3.3))
for ax, (key, title) in zip(axs, titles.items()):
    g = groups[key]
    xs = [num(r["value"]) for r in g]
    ax.plot(xs, [num(r["mean_A"]) for r in g], marker="o", ms=4.5, lw=1.7, color=COL["A"], label="конфігурація A")
    ax.plot(xs, [num(r["mean_C"]) for r in g], marker="o", ms=4.5, lw=1.7, color=COL["C"], label="конфігурація C")
    ax2 = ax.twinx()
    ax2.bar(xs, [int(r["unobservable C, min"]) for r in g], width=(max(xs)-min(xs))/18,
            color="#bcccdc", alpha=.55, zorder=0)
    ax2.set_ylim(0, 70); ax2.set_yticks([0, 30, 60])
    if ax is axs[-1]: ax2.set_ylabel("неспостережуваність C, хв", fontsize=8)
    else: ax2.set_yticklabels([])
    ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)
    ax.set_title(title, fontsize=9.2); ax.set_ylim(0, 0.62); ax.grid(alpha=.3, lw=.5)
    ax.yaxis.set_major_formatter(comma)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:g}".replace(".", ",")))
axs[0].set_ylabel("$\\bar{O}$, аварійний інтервал")
axs[0].legend(fontsize=8, frameon=False, loc="upper left")
plt.tight_layout()
plt.savefig(OUT + "/fig_sensitivity.png", dpi=300, bbox_inches="tight")
plt.close()

# ---------------- масштабованість ----------------
sc = load("scalability.csv")
n = [int(r["nodes"]) for r in sc]
ms = [num(r["median ms/step"]) for r in sc]
ed = [int(r["mean directed edges"]) for r in sc]
fig, ax = plt.subplots(figsize=(6.4, 3.6))
ax.loglog(n, ms, marker="o", ms=6, lw=1.8, color=NAVY, label="час обчислення на крок")
for x, y, e in zip(n, ms, ed):
    ax.annotate(f"{e} ребер", (x, y), textcoords="offset points", xytext=(0, 9), ha="center",
                fontsize=7.4, color=GREY)
ax.set_xlabel("кількість вузлів")
ax.set_ylabel("час на крок, мс")
ax.set_ylim(1.0, 3e3)
ax.set_xlim(20, 380)
ax.grid(alpha=.3, which="both", lw=.5)

plt.tight_layout()
plt.savefig(OUT + "/fig_scalability.png", dpi=300, bbox_inches="tight")
plt.close()

# ---------------- ablation ----------------
ab = load("ablation.csv")
methods = [("snapshot connectivity", "миттєва зв'язність\nзнімка"),
           ("static aggregated graph", "статичний\nагрегований граф"),
           ("temporal reachability, no freshness", "темпоральна досяжність\nбез віку та достовірності"),
           ("proposed (full)", "запропонований\nметод")]
fig, ax = plt.subplots(figsize=(7.4, 3.6))
width = 0.24
for i, (cfg, row) in enumerate(zip("ABC", ab)):
    xs = [j + (i - 1) * width for j in range(len(methods))]
    ax.bar(xs, [num(row[k]) for k, _ in methods], width * 0.92,
           color=COL[cfg], label=f"конфігурація {cfg}")
    for x, k in zip(xs, [k for k, _ in methods]):
        ax.text(x, num(row[k]) + 0.012, f"{num(row[k]):.3f}".replace(".", ","),
                ha="center", fontsize=6.9, color="#333")
ax.set_xticks(range(len(methods)))
ax.set_xticklabels([lbl for _, lbl in methods], fontsize=8.4)
ax.set_ylabel("$\\bar{O}$, аварійний інтервал")
ax.set_ylim(0, 0.82)
ax.yaxis.set_major_formatter(comma)
ax.grid(alpha=.3, axis="y", lw=.5)
ax.legend(fontsize=8.4, frameon=False, ncol=3, loc="upper left")
plt.tight_layout()
plt.savefig(OUT + "/fig_ablation.png", dpi=300, bbox_inches="tight")
plt.close()

# ---------------- критичність ----------------
import model2 as M
from model2 import CONFIGS, mean, run
base = mean(run("C")[0])
crit = sorted(((n_, base - mean(run("C", removed=(n_,))[0])) for n_ in CONFIGS["C"] if n_ != "CC"),
              key=lambda x: x[1])
names = [n_ for n_, _ in crit]
vals = [v for _, v in crit]
kind = {"sensor": "#2a9d8f", "uav": "#8e44ad", "service": "#e76f51",
        "tanker": "#6c757d", "worker": "#d4a017", "relay": "#3b6fb6"}
cols = [kind[M.NODES[n_]["type"]] for n_ in names]
fig, ax = plt.subplots(figsize=(6.4, 4.0))
ax.barh(names, vals, color=cols, height=.68)
for i, v in enumerate(vals):
    ax.text(v + 0.0016, i, f"{v:.3f}".replace(".", ","), va="center", fontsize=7.6, color="#333")
ax.set_xlabel("критичність $\\chi(v)$")
ax.set_xlim(0, max(vals) * 1.22)
ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: f"{v:.2f}".replace(".", ",")))
ax.grid(alpha=.3, axis="x", lw=.5)
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in
           ["#2a9d8f", "#3b6fb6", "#e76f51", "#6c757d", "#8e44ad", "#d4a017"]]
ax.legend(handles, ["буй", "береговий шлюз", "судно портового флоту",
                    "танкер", "БПЛА", "працівник"], fontsize=7.6, frameon=False,
          loc="lower right")
plt.tight_layout()
plt.savefig(OUT + "/fig_criticality.png", dpi=300, bbox_inches="tight")
plt.close()
print("ok")
