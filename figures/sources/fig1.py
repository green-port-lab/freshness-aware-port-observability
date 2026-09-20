import os, matplotlib
matplotlib.use("Agg")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
os.makedirs(OUT, exist_ok=True)
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({"font.family": "DejaVu Sans"})
fig, ax = plt.subplots(figsize=(10, 8.6))
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

NAVY, BLUE, TEAL, ORANGE, GREEN = "#1f2d5a", "#3b6fb6", "#2a9d8f", "#e76f51", "#2e7d32"

def box(x, y, w, h, title, body=None, ec=BLUE, fc="#f4f7fc", tsize=9.5, bsize=8, dashed=False, tcolor=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2",
                                ec=ec, fc=fc, lw=1.3, ls="--" if dashed else "-"))
    if body:
        ax.text(x + w / 2, y + h - 2.2, title, ha="center", va="top", fontsize=tsize, weight="bold",
                color=tcolor or NAVY)
        ax.text(x + w / 2, y + h - 5.6, body, ha="center", va="top", fontsize=bsize, color="#333",
                linespacing=1.35)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=tsize, weight="bold",
                color=tcolor or NAVY, linespacing=1.3)

def arrow(x1, y1, x2, y2, color="#4a5b6e", style="-|>", lw=1.2, ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=12,
                                 color=color, lw=lw, ls=ls))

# --- Учасники ---
ax.text(50, 98.5, "Учасники порту як вершини темпорального графа $\\mathcal{G}$", ha="center", va="top",
        fontsize=10.5, weight="bold", color=NAVY)
parts = ["Датчики\nводного\nсередовища", "Судна\n(AIS, радіо,\nсенсори)", "Берегові\nшлюзи LoRaWAN\nі станції",
         "БПЛА", "Працівники\n(рація,\nUWB-бейдж)", "Центр\nкерування"]
pw, gap = 14.2, 1.6
x0 = (100 - (6 * pw + 5 * gap)) / 2
for i, p in enumerate(parts):
    box(x0 + i * (pw + gap), 83, pw, 10.5, p, tsize=8.2)

# --- Два контури ---
box(2, 45, 45, 32, "", ec=TEAL)
ax.text(24.5, 76, "Контур об’єкта спостереження", ha="center", va="top", fontsize=10, weight="bold", color=TEAL)
ax.text(24.5, 72.6, "стан акваторії X(t)", ha="center", va="top", fontsize=8.5, style="italic", color="#333")
box(5, 58, 39, 10.5, "Фізико-хімічний рівень $X_{\\mathrm{ф}}$",
    "температура, pH, солоність, каламутність,\nрозчинений кисень, забруднювачі", ec=TEAL, fc="white", tsize=8.8, bsize=7.6)
box(5, 47, 39, 9.5, "Просторово-динамічний рівень $X_{\\mathrm{п}}$",
    "зони $z_k$, перенос між зонами,\nпоширення плями", ec=TEAL, fc="white", tsize=8.8, bsize=7.6)

box(53, 45, 45, 32, "", ec=ORANGE)
ax.text(75.5, 76, "Контур системи спостереження", ha="center", va="top", fontsize=10, weight="bold", color=ORANGE)
ax.text(75.5, 72.6, "мережа $\\mathcal{G}$(t) та якість даних I(t)", ha="center", va="top", fontsize=8.5, style="italic", color="#333")
box(56, 58, 39, 10.5, "Мережево-операційний рівень",
    "темпоральний граф учасників, стан вузлів\nі каналів, готовність засобів реагування", ec=ORANGE, fc="white", tsize=8.8, bsize=7.6)
box(56, 47, 39, 9.5, "Інформаційний рівень",
    "вік даних $\\Delta_k(t)$, достовірність q,\nузгодженість джерел", ec=ORANGE, fc="white", tsize=8.8, bsize=7.6)

# стрілки від учасників
for i in range(6):
    cx = x0 + i * (pw + gap) + pw / 2
    ax.plot([cx, cx], [82.3, 80.8], color="#4a5b6e", lw=1.1)
ax.plot([x0 + pw / 2, x0 + 5 * (pw + gap) + pw / 2], [80.8, 80.8], color="#4a5b6e", lw=1.1)
arrow(24.5, 80.8, 24.5, 77.6); arrow(75.5, 80.8, 75.5, 77.6)
# відношення спостереження між контурами
arrow(53, 63, 47, 63, color=NAVY, style="<|-|>")
ax.text(50, 65.2, r"$\sigma(v, z, t)$", ha="center", fontsize=8.3, color=NAVY, style="italic")
ax.text(50, 60.2, "відношення\nспостереження", ha="center", va="top", fontsize=7, color="#555")

# --- Критерій ---
arrow(24.5, 44.3, 40, 40.2); arrow(75.5, 44.3, 60, 40.2)
box(14, 30.5, 72, 9, "Критерій і показник спостережуваності",
    "Δ-спостережуваність за часово-узгодженими шляхами в $\\mathcal{G}$  ·  O(t)  ·  критичність вузлів",
    ec=NAVY, fc="#e8eef8", tsize=9.5, bsize=8)
arrow(50, 29.8, 50, 26.6)

# --- Практичні результати ---
box(3, 13.5, 94, 12.5, "", ec=BLUE, fc="white", dashed=True)
ax.text(50, 25.4, "Практичні результати", ha="center", va="top", fontsize=9.5, weight="bold", color=BLUE)
res = ["Виявлення\nзабруднення", "Оцінювання\nризику", "Прогнозування\nпоширення", "Резервування\nмережі", "Підтримка\nрішень"]
rw = 16.6
for i, r in enumerate(res):
    box(5.5 + i * (rw + 1.8), 15, rw, 6.3, r, tsize=7.8, fc="#f4f7fc")
arrow(50, 12.8, 50, 10.2)

box(10, 1.5, 80, 8, "Концепція «зеленого порту»",
    "екологічна результативність  |  моніторинг  |  аварійне реагування  |  сталий розвиток",
    ec=GREEN, fc="#eef6ee", tsize=9.5, bsize=7.8, tcolor=GREEN)

plt.savefig(OUT + "/fig1_scheme.png", dpi=300, bbox_inches="tight")
print("ok")
