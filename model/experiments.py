"""
Computational evaluation for the freshness-aware observability framework.

Produces:
  results2/ablation.csv      four methods x three configurations
  results2/sensitivity.csv   Dmax, kappa, worker reliability, time step
  results2/factorial.csv     node loss x link degradation, 2x2 design
  results2/scalability.csv   runtime vs network size
  results2/static_gap.csv    pointwise gap of the static aggregated graph

Usage:  python src/experiments.py
"""
import csv, math, os, random, statistics, sys, time
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model2 as M
from model2 import (CONFIGS, DMAX, PARAMS, FLAGS, TIMES, T_END, W, ZONES,
                    mean, run, run_static, run_snapshot, run_nofreshness, spill_times)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
os.makedirs(OUT, exist_ok=True)
CFGS = ["A", "B", "C"]
SP = spill_times()
CRISIS = (60, 115)


def crisis_mean(O):
    """Середнє за аварійний інтервал [60, 120), коректне для будь-якого кроку.

    CRISIS = (60, 115) описує той самий інтервал лише при кроці 5 хв, де момент 115
    представляє проміжок [115, 120). Для інших кроків треба брати всі моменти з [60, 120).
    """
    v = [O[t] for t in O if CRISIS[0] <= t < CRISIS[1] + 5]
    return sum(v) / len(v)

def r(x, n=3):
    return str(Decimal(repr(round(x, 9))).quantize(Decimal(1).scaleb(-n), ROUND_HALF_UP))

def write(name, header, rows):
    p = os.path.join(OUT, name)
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    print("wrote", os.path.relpath(p))

def reset():
    PARAMS.update(kappa=0.5, dmax_scale=1.0, q_scale=1.0, dt=5)
    FLAGS.update(jam=True, destroy=True)
    M.TYPES["worker"]["q"] = 0.5

# ---------------- 1. Ablation ----------------
def ablation():
    rows = []
    for cfg in CFGS:
        reset()
        rows.append([cfg,
                     r(mean(run_snapshot(cfg), *CRISIS)),
                     r(mean(run_static(cfg), *CRISIS)),
                     r(mean(run_nofreshness(cfg), *CRISIS)),
                     r(mean(run(cfg)[0], *CRISIS))])
    write("ablation.csv",
          ["configuration", "snapshot connectivity", "static aggregated graph",
           "temporal reachability, no freshness", "proposed (full)"], rows)
    return rows

# ---------------- 2. Static-graph gap ----------------
def static_gap():
    rows = []
    for cfg in CFGS:
        reset()
        Ot, Os = run(cfg)[0], run_static(cfg)
        diff = [(t, Os[t] - Ot[t]) for t in TIMES if CRISIS[0] <= t <= CRISIS[1]]
        tmax, dmaxv = max(diff, key=lambda x: x[1])
        trans = max(Os[t] - Ot[t] for t in TIMES if t < CRISIS[0])
        rows.append([cfg, r(mean(Os, *CRISIS)), r(mean(Ot, *CRISIS)),
                     r(mean(Os, *CRISIS) - mean(Ot, *CRISIS)), r(dmaxv), tmax,
                     sum(1 for _, d in diff if d > 1e-9), r(trans)])
    write("static_gap.csv",
          ["configuration", "static mean (60-115)", "proposed mean (60-115)",
           "mean overestimate", "max pointwise overestimate", "at t, min",
           "steps with overestimate", "max on start-up transient"], rows)
    return rows

# ---------------- 3. Factorial ----------------
def factorial():
    rows = []
    for cfg in CFGS:
        reset()
        vals = {}
        for jam in (False, True):
            for des in (False, True):
                FLAGS.update(jam=jam, destroy=des)
                vals[(jam, des)] = mean(run(cfg)[0], *CRISIS)
        reset()
        base = vals[(False, False)]
        l_des = base - vals[(False, True)]
        l_jam = base - vals[(True, False)]
        l_both = base - vals[(True, True)]
        rows.append([cfg, r(base), r(vals[(False, True)]), r(vals[(True, False)]),
                     r(vals[(True, True)]), r(l_des), r(l_jam), r(l_both),
                     r(l_both - l_des - l_jam)])
    write("factorial.csv",
          ["configuration", "no failures", "node loss only", "link degradation only",
           "both", "loss: node", "loss: link", "loss: both", "interaction"], rows)
    return rows

# ---------------- 4. Sensitivity ----------------
def sensitivity():
    rows = []
    def record(param, value):
        vals = {c: mean(run(c)[0], *CRISIS) for c in CFGS}
        order = "yes" if vals["A"] <= vals["B"] <= vals["C"] else "NO"
        rows.append([param, value, r(vals["A"]), r(vals["B"]), r(vals["C"]),
                     r(vals["C"] - vals["A"]), order])
    for s in (0.5, 0.75, 1.0, 1.5, 2.0):
        reset(); PARAMS["dmax_scale"] = s
        record("admissible age scale", s)
    for k in (0.3, 0.4, 0.5, 0.7, 0.9):
        reset(); PARAMS["kappa"] = k
        record("link degradation kappa", k)
    for q in (0.3, 0.4, 0.5, 0.7, 0.9):
        reset(); M.TYPES["worker"]["q"] = q
        record("worker reliability q", q)
    for dt in (1, 2, 5, 10):
        reset(); PARAMS["dt"] = dt
        vals = {c: crisis_mean(run(c, dt=dt)[0]) for c in CFGS}
        order = "yes" if vals["A"] <= vals["B"] <= vals["C"] else "NO"
        rows.append(["time step, min", dt, r(vals["A"]), r(vals["B"]), r(vals["C"]),
                     r(vals["C"] - vals["A"]), order])
    reset()
    write("sensitivity.csv",
          ["parameter", "value", "A", "B", "C", "C - A", "ordering A<=B<=C preserved"], rows)
    return rows

# ---------------- 5. Scalability ----------------
def synthetic(n_nodes, n_zones, seed=0):
    """Синтетична мережа: n_zones зон у сітці, n_nodes вузлів, один центр керування."""
    rnd = random.Random(seed)
    side = math.ceil(math.sqrt(n_zones))
    zones = {}
    for i in range(n_zones):
        cx, cy = (i % side) * .5, (i // side) * .5
        zones[i + 1] = ((cx, cx + .5), (cy, cy + .5))
    M.ZONES.clear(); M.ZONES.update(zones)
    M.W.clear(); M.W.update({k: 1 for k in zones})
    M.DMAX.clear(); M.DMAX.update({k: 20 for k in zones})
    span = side * .5
    nodes = {"CC": dict(type="CC", pos=lambda t: (span / 2, -.25), life=(0, 999))}
    for i in range(n_nodes - 1):
        x, y = rnd.uniform(0, span), rnd.uniform(0, span)
        if i % 3 == 0:
            z = rnd.randint(1, n_zones)
            nodes[f"S{i}"] = dict(type="sensor", pos=(lambda x=x, y=y: (lambda t: (x, y)))(),
                                  life=(0, 999), zone=z)
        elif i % 3 == 1:
            nodes[f"R{i}"] = dict(type="relay", pos=(lambda x=x, y=y: (lambda t: (x, y)))(),
                                  life=(0, 999))
        else:
            nodes[f"V{i}"] = dict(type="service", life=(0, 999),
                                  pos=(lambda x=x, y=y, s=span: (lambda t: (
                                      (x + t * 0.01) % s, y)))())
    M.NODES.clear(); M.NODES.update(nodes)
    M.CONFIGS["S"] = list(nodes)

def scalability():
    """Час обчислення одного кроку: мінімум, медіана й максимум за повторами.

    Повторів: 5 для мереж до 100 вузлів, 3 для 250 (через тривалість прогону).
    Кількість ребер усереднюється за знімками t = 0, 50, 100 хв.
    """
    saveZ, saveW, saveD = dict(M.ZONES), dict(M.W), dict(M.DMAX)
    saveN, saveC = dict(M.NODES), dict(M.CONFIGS)
    rows = []
    for n in (25, 50, 100, 250):
        nz = max(12, n // 4)
        synthetic(n, nz)
        reps = 5 if n <= 100 else 3
        steps = len(M.TIMES)
        ts = []
        for _ in range(reps):
            t0 = time.perf_counter()
            run("S")
            ts.append((time.perf_counter() - t0) * 1000 / steps)
        edges = statistics.mean(len(M.edges_at(t, list(M.NODES))) for t in (0, 50, 100))
        rows.append([n, nz, int(edges), r(min(ts), 2), r(statistics.median(ts), 2),
                     r(max(ts), 2), r(100 * statistics.median(ts) / 300000, 4)])
        print(f"  {n} вузлів, {nz} зон, ~{int(edges)} ребер, {reps} повторів: "
              f"медіана {statistics.median(ts):.2f} мс/крок")
    M.ZONES.clear(); M.ZONES.update(saveZ)
    M.W.clear(); M.W.update(saveW)
    M.DMAX.clear(); M.DMAX.update(saveD)
    M.NODES.clear(); M.NODES.update(saveN)
    M.CONFIGS.clear(); M.CONFIGS.update(saveC)
    write("scalability.csv",
          ["nodes", "zones", "mean directed edges", "min ms/step", "median ms/step",
           "max ms/step", "share of 5-min budget, %"], rows)
    return rows


# ---------------- 6. Розділення внесків свіжості та достовірності ----------------
def components():
    from model2 import DMAX, ZONES, W, TYPES, NODES, active, edges_at, sensing_at, propagate, _add, _best, _prune

    def variant(cfg, use_age=True, use_q=True, dt=5):
        times = list(range(0, M.T_END + 1, dt))
        store = {n: {} for n in CONFIGS[cfg]}
        O = {}
        for t in times:
            act = [n for n in CONFIGS[cfg] if active(n, t)]
            for n in CONFIGS[cfg]:
                if n not in act:
                    store[n] = {}
            for n in act:
                for k in sensing_at(t, n):
                    _add(store[n], (k, NODES[n]["type"]), t, t)
            for n in act:
                _prune(store[n], t)
            sub = propagate({n: store[n] for n in act}, edges_at(t, act), dt, t)
            for n in act:
                store[n] = sub[n]
            cc, num = store["CC"], 0.0
            for k in ZONES:
                best = 0.0
                for (kk, ty) in cc:
                    if kk != k:
                        continue
                    tau = _best(cc, (kk, ty), t)
                    if tau is None or (use_age and t - tau > DMAX[k]):
                        continue
                    best = max(best, TYPES[ty]["q"] if use_q else 1.0)
                num += W[k] * best
            O[t] = num / sum(W.values())
        return O

    rows = []
    for label, ua, uq in [("повний, вік і достовірність", True, True),
                          ("без ваг достовірності", True, False),
                          ("без обмеження віку", False, True),
                          ("без обох складників", False, False)]:
        reset()
        rows.append([label] + [r(mean(variant(c, ua, uq), *CRISIS)) for c in CFGS])
    write("ablation_components.csv", ["variant"] + CFGS, rows)
    return rows


# ---------------- 7. Контрольний прогін без відмов ----------------
def control_run():
    CRIT = [1, 2]

    def unobservable(cfg, dt=5):
        O, AGE, _ = run(cfg, spill=SP, dt=dt)
        n = 0
        for t in [x for x in sorted(O) if CRISIS[0] <= x <= CRISIS[1]]:
            for k in CRIT:
                a = AGE[t][k]
                if a is None or a > DMAX[k] * PARAMS["dmax_scale"]:
                    n += dt
                    break
        return n

    rows = []
    reset(); main = {c: unobservable(c) for c in CFGS}
    FLAGS.update(jam=False, destroy=False)
    ctrl = {c: unobservable(c) for c in CFGS}
    reset()
    for c in CFGS:
        rows.append([c, ctrl[c], main[c], main[c] - ctrl[c]])
    write("control_run.csv", ["configuration", "control, min", "main scenario, min",
                              "increment, min"], rows)
    return rows


# ---------------- 8. Чутливість: змістовні показники ----------------
def sensitivity_effects():
    CRIT = [1, 2]

    def metrics(cfg, dt=5):
        O, AGE, fs = run(cfg, spill=SP, dt=dt)
        lost = 0
        for t in [x for x in sorted(O) if CRISIS[0] <= x <= CRISIS[1]]:
            for k in CRIT:
                a = AGE[t][k]
                if a is None or a > DMAX[k] * PARAMS["dmax_scale"]:
                    lost += dt
                    break
        return mean(O, *CRISIS), lost, (fs[1] - SP[1] if 1 in fs else None)

    rows = []

    def rec(p, v):
        m = {c: metrics(c) for c in CFGS}
        rows.append([p, v, r(m["A"][0]), r(m["C"][0]), r(m["C"][0] - m["A"][0]),
                     f"{(m['C'][0]-m['A'][0])/m['A'][0]*100:.0f}" if m["A"][0] > 0 else "n/d",
                     m["A"][1], m["C"][1],
                     "n/d" if m["A"][2] is None else m["A"][2],
                     "n/d" if m["C"][2] is None else m["C"][2]])

    for v in (0.5, 0.75, 1.0, 1.5, 2.0):
        reset(); PARAMS["dmax_scale"] = v; rec("admissible age scale", v)
    for v in (0.3, 0.4, 0.5, 0.7, 0.9):
        reset(); PARAMS["kappa"] = v; rec("kappa", v)
    for v in (0.3, 0.5, 0.9):
        reset(); M.TYPES["worker"]["q"] = v; rec("worker reliability", v)
    reset()
    write("sensitivity_effects.csv",
          ["parameter", "value", "mean_A", "mean_C", "gain", "gain, %",
           "unobservable A, min", "unobservable C, min", "delay Z1 A", "delay Z1 C"], rows)
    return rows


# ---------------- 9. Просторове огрублення положень працівників ----------------
def quantization():
    orig = {n: M.NODES[n]["pos"] for n in M.NODES}

    def grid(node, cell):
        f = orig[node]
        return lambda t: (math.floor(f(t)[0] / cell) * cell + cell / 2,
                          math.floor(f(t)[1] / cell) * cell + cell / 2)

    reset()
    base = {c: run(c, spill=SP) for c in CFGS}
    rows = []
    for cell in (0.25, 0.5):
        for n in ("W1", "W2", "W3"):
            M.NODES[n]["pos"] = grid(n, cell)
        q = {c: run(c, spill=SP) for c in CFGS}
        for n in ("W1", "W2", "W3"):
            M.NODES[n]["pos"] = orig[n]
        for c in CFGS:
            b, qq = base[c][0], q[c][0]
            dmx = max(abs(qq[t] - b[t]) for t in TIMES)
            d1b, d1q = base[c][2].get(1), q[c][2].get(1)
            rows.append([cell, c, r(mean(b, *CRISIS)), r(mean(qq, *CRISIS)),
                         r(mean(qq, *CRISIS) - mean(b, *CRISIS)), r(dmx),
                         "n/d" if d1b is None else d1b - SP[1],
                         "n/d" if d1q is None else d1q - SP[1]])
    write("privacy_quantization.csv",
          ["cell, km", "configuration", "exact", "quantized", "difference",
           "max pointwise", "delay Z1 exact", "delay Z1 quantized"], rows)
    return rows


# ---------------- 10. Розмір буфера ----------------
def buffer_size():
    from model2 import active, edges_at, sensing_at, propagate, _add, _prune, NODES
    reset()
    maxP = maxD = 0
    store = {n: {} for n in CONFIGS["C"]}
    def scan(t):
        nonlocal maxP, maxD
        for buf in store.values():
            for pairs in buf.values():
                maxP = max(maxP, len(pairs))
            deps = {max(a, t) for pairs in buf.values() for _, a in pairs if max(a, t) < t + 5}
            maxD = max(maxD, len(deps))
    for t in M.TIMES:
        act = [n for n in CONFIGS["C"] if active(n, t)]
        for n in CONFIGS["C"]:
            if n not in act:
                store[n] = {}
        for n in act:
            for k in sensing_at(t, n):
                _add(store[n], (k, NODES[n]["type"]), t, t)
        scan(t)
        for n in act:
            _prune(store[n], t)
        scan(t)
        sub = propagate({n: store[n] for n in act}, edges_at(t, act), 5, t)
        for n in act:
            store[n] = sub[n]
        scan(t)
    write("buffer_size.csv", ["max P", "max D"], [[maxP, maxD]])
    return maxP, maxD


# ---------------- 11. Robustness of the headline results to the time step ----------------
def robustness_time_step():
    """Головні показники при базовому кроці 5 хв і при кроці 1 хв (Appendix B)."""
    def avg(O, a, b):
        v = [O[t] for t in O if a <= t < b]
        return sum(v) / len(v)
    out = {}
    for dt in (5, 1):
        reset()
        O = {c: run(c, spill=SP, dt=dt) for c in CFGS}
        S = {c: run_static(c, dt=dt) for c in ("B", "C")}
        d = {}
        for c in CFGS:
            Oc = O[c][0]
            d[f"mean score, normal operation [5,60), {c}"] = avg(Oc, 5, 60)
            d[f"mean score, accident interval [60,120), {c}"] = avg(Oc, 60, 120)
            d[f"mean score, after recovery [120,180], {c}"] = avg(Oc, 120, 181)
        for c in ("B", "C"):
            g = {t: S[c][t] - O[c][0][t] for t in S[c]}
            d[f"static graph, max discrepancy over [60,120), {c}"] = max(v for t, v in g.items() if 60 <= t < 120)
            d[f"static graph, mean discrepancy over [60,120), {c}"] = avg(g, 60, 120)
        for c in CFGS:
            vals = {}
            for jam, des in ((False, False), (False, True), (True, False), (True, True)):
                reset(); FLAGS.update(jam=jam, destroy=des)
                vals[(jam, des)] = avg(run(c, spill=SP, dt=dt)[0], 60, 120)
            base = vals[(False, False)]
            d[f"factorial interaction, {c}"] = (base - vals[(True, True)]) - (base - vals[(False, True)]) - (base - vals[(True, False)])
        reset()
        for c in CFGS:
            fs = O[c][2]
            for k in (1, 2, 5):
                d[f"detection delay Z{k}, min, {c}"] = (fs[k] - SP[k]) if k in fs else None
        out[dt] = d
    rows = []
    for key in out[5]:
        f = lambda v: "n.d." if v is None else (v if isinstance(v, int) else r(v))
        rows.append([key, f(out[5][key]), f(out[1][key])])
    write("robustness_time_step.csv", ["indicator", "time step 5 min", "time step 1 min"], rows)
    return rows


if __name__ == "__main__":
    print("=== 1. ablation (Table 5) ==="); [print("  ", x) for x in ablation()]
    print("=== 2. components (Table 6) ==="); [print("  ", x) for x in components()]
    print("=== 3. static gap (Section 5.3) ==="); [print("  ", x) for x in static_gap()]
    print("=== 4. factorial (Table 7) ==="); [print("  ", x) for x in factorial()]
    print("=== 5. sensitivity effects (Table 8) ==="); [print("  ", x) for x in sensitivity_effects()]
    print("=== 5b. sensitivity, incl. time step (Section 5.5) ==="); [print("  ", x) for x in sensitivity()]
    print("=== 6. control run (Table 9) ==="); [print("  ", x) for x in control_run()]
    print("=== 7. buffer size (Section 3.8) ==="); print("  P, D =", buffer_size())
    print("=== 8. quantization (Section 6.3) ==="); [print("  ", x) for x in quantization()]
    print("=== 9. robustness to the time step (Appendix B) ==="); [print("  ", x) for x in robustness_time_step()]
    print("=== 10. scalability (Table 10) ==="); scalability()
