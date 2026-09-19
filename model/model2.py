"""
Freshness-aware temporal-graph observability model of a port water area (v2).

Changes with respect to v1:
  * communication links are DIRECTED: LoRaWAN end devices are uplink-only,
    radio and wired links are bidirectional;
  * link latency zeta is NON-ZERO and channel-specific;
  * data propagation inside a snapshot is an earliest-arrival (Dijkstra)
    computation bounded by the step DT, instead of connected components;
  * store-carry-forward between snapshots is unchanged.

Standard library only. Python 3.9+.
Usage:  python model2.py
"""
import heapq
import itertools
import math
from collections import defaultdict

DT = 5            # крок дискретизації, хв
T_END = 180       # горизонт, хв
TIMES = list(range(0, T_END + 1, DT))

# ---------- Акваторія ----------
ZONES = {}
for r in range(3):
    for c in range(4):
        ZONES[r * 4 + c + 1] = ((c * .5, c * .5 + .5), (r * .5, r * .5 + .5))

def zone_center(k):
    (x0, x1), (y0, y1) = ZONES[k]
    return ((x0 + x1) / 2, (y0 + y1) / 2)

def zone_of(p):
    x, y = p
    for k, ((x0, x1), (y0, y1)) in ZONES.items():
        if x0 <= x < x1 and y0 <= y < y1:
            return k
    return None

W = {k: 1 for k in ZONES}
for k in (1, 2): W[k] = 3
for k in (5, 6, 10, 11): W[k] = 2
DMAX = {k: {3: 10, 2: 20, 1: 30}[W[k]] for k in ZONES}

# ---------- Канали зв'язку: дальність (км), затримка (хв), напрям ----------
# 'uplink' означає, що кінцевий пристрій може лише передавати до шлюзу
CHANNELS = {
    "wired":  dict(rng=99.0, lat=0.10, sym=True),
    "radio":  dict(rng=None, lat=0.20, sym=True),
    "lora":   dict(rng=1.60, lat=1.00, sym=False),
}

# ---------- Типи учасників ----------
# ch: канали; gw: чи є шлюзом LoRaWAN (може приймати uplink); r: дальність радіо
TYPES = {
    "CC":      dict(ch={"radio"},         r=1.5, q=None, gw=False),
    "relay":   dict(ch={"radio", "lora"}, r=1.6, q=None, gw=True),
    "sensor":  dict(ch={"lora"},          r=1.6, q=1.0,  gw=False),
    "tanker":  dict(ch={"radio"},         r=3.0, q=None, gw=False),
    "service": dict(ch={"radio", "lora"}, r=2.0, q=0.9,  gw=True),
    "uav":     dict(ch={"radio", "lora"}, r=2.0, q=0.8,  gw=True),
    "worker":  dict(ch={"radio"},         r=1.0, q=0.5,  gw=False),
}
WIRED = {("CC", "R1"), ("CC", "R2")}

def lin(wp, t):
    if t <= wp[0][0]:
        return wp[0][1:]
    for (t0, x0, y0), (t1, x1, y1) in zip(wp, wp[1:]):
        if t0 <= t <= t1:
            a = (t - t0) / (t1 - t0) if t1 > t0 else 1
            return (x0 + a * (x1 - x0), y0 + a * (y1 - y0))
    return wp[-1][1:]

NODES = {
    "CC": dict(type="CC",     pos=lambda t: (1.6, -0.25), life=(0, 999)),
    "R1": dict(type="relay",  pos=lambda t: (0.4, -0.10), life=(0, 60)),
    "R2": dict(type="relay",  pos=lambda t: (1.6, -0.10), life=(0, 999)),
    "S1": dict(type="sensor", pos=lambda t: (0.25, 0.30), life=(0, 60), zone=1),
    "S2": dict(type="sensor", pos=lambda t: (1.25, 0.30), life=(0, 999), zone=3),
    "S3": dict(type="sensor", pos=lambda t: (0.75, 0.75), life=(0, 999), zone=6),
    "S4": dict(type="sensor", pos=lambda t: (1.75, 0.75), life=(0, 999), zone=8),
    "S5": dict(type="sensor", pos=lambda t: (0.75, 1.25), life=(0, 999), zone=10),
    "S6": dict(type="sensor", pos=lambda t: (1.75, 1.25), life=(0, 999), zone=12),
    "V1": dict(type="tanker", life=(0, 150),
               pos=lambda t: lin([(0, .80, .12), (120, .80, .12), (135, .90, 1.0), (150, 1.1, 1.9)], t)),
    "V2": dict(type="service", life=(0, 999),
               pos=lambda t: lin([(0, 1.65, .15), (70, 1.65, .15), (90, .70, .65), (100, .30, .35)], t)),
    "D1": dict(type="uav", life=(90, 170),
               pos=lambda t: (lin([(90, 1.6, -.25), (100, .5, .5)], t) if t <= 100 else
                              (.5 + .3 * math.cos((t - 100) / 10), .5 + .3 * math.sin((t - 100) / 10)))),
    "W1": dict(type="worker", life=(0, 999),
               pos=lambda t: lin([(0, .50, -.05), (60, .50, -.05), (65, .90, -.45),
                                  (100, .90, -.45), (105, .50, -.05)], t)),
    "W2": dict(type="worker", life=(0, 999),
               pos=lambda t: lin([(0, 1.0, -.05), (60, 1.0, -.05), (65, .95, -.45),
                                  (95, .95, -.45), (100, 1.0, -.05)], t)),
    "W3": dict(type="worker", pos=lambda t: (1.75, -.05), life=(0, 999)),
}

PARAMS = dict(kappa=0.5, jam=(60, 120), dmax_scale=1.0, q_scale=1.0, dt=DT)
FLAGS = {"jam": True, "destroy": True}

def kappa(t):
    a, b = PARAMS["jam"]
    return PARAMS["kappa"] if (FLAGS["jam"] and a <= t < b) else 1.0

def active(n, t, removed=()):
    a, b = NODES[n]["life"]
    if not FLAGS["destroy"] and n in ("R1", "S1"):
        b = 999
    return n not in removed and a <= t < b

def edges_at(t, nodes):
    """Орієнтовані ребра (u -> v, затримка). Датчики LoRaWAN передають лише до шлюзів."""
    out = []
    for u, v in itertools.permutations(nodes, 2):
        tu, tv = TYPES[NODES[u]["type"]], TYPES[NODES[v]["type"]]
        if (u, v) in WIRED or (v, u) in WIRED:
            out.append((u, v, CHANNELS["wired"]["lat"]))
            continue
        d = math.dist(NODES[u]["pos"](t), NODES[v]["pos"](t))
        # радіо: симетричний канал
        if "radio" in tu["ch"] and "radio" in tv["ch"]:
            if d <= min(tu["r"], tv["r"]) * kappa(t):
                out.append((u, v, CHANNELS["radio"]["lat"]))
                continue
        # LoRaWAN: кінцевий пристрій -> шлюз, лише вгору
        if "lora" in tu["ch"] and "lora" in tv["ch"] and tv["gw"] and not tu["gw"]:
            if d <= CHANNELS["lora"]["rng"] * kappa(t):
                out.append((u, v, CHANNELS["lora"]["lat"]))
    return out

def sensing_at(t, n):
    ty = NODES[n]["type"]
    if ty == "sensor":
        return {NODES[n]["zone"]}
    p = NODES[n]["pos"](t)
    if ty == "service":
        z = zone_of(p); return {z} if z else set()
    if ty == "uav":
        return {k for k in ZONES if math.dist(p, zone_center(k)) <= 0.45}
    if ty == "worker":
        return set() if p[1] < -0.2 else {k for k in ZONES if math.dist(p, zone_center(k)) <= 0.40}
    return set()

CONFIGS = {
    "A": [n for n in NODES if NODES[n]["type"] in ("CC", "relay", "sensor")],
    "B": [n for n in NODES if NODES[n]["type"] in ("CC", "relay", "sensor", "tanker", "service")],
    "C": list(NODES),
}

def _add(buf, key, tau, avail):
    """Додає пару (tau, avail) і лишає лише недоміновані: (t1,a1) домінує (t2,a2),
    якщо t1 >= t2 і a1 <= a2."""
    items = list(buf.get(key, ()))
    for tt, aa in items:
        if tt >= tau and aa <= avail:
            return
    items = [(tt, aa) for tt, aa in items if not (tau >= tt and avail <= aa)]
    items.append((tau, avail))
    buf[key] = tuple(items)


def _best(buf, key, t):
    """Найсвіжіший момент формування серед пар, доставлених до моменту t."""
    best = None
    for tau, av in buf.get(key, ()):
        if av <= t and (best is None or tau > best):
            best = tau
    return best


def _prune(buf, t):
    """Згортання буфера без зміни семантики.

    Усі пари, доступні до моменту t, рівноцінні й замінюються найсвіжішою з них.
    Пари, що перебувають у дорозі, зберігаються незалежно від віку, якщо вони
    свіжіші за вже доставлену: вони ще можуть уточнити величину tau_k(t).
    """
    for key, pairs in list(buf.items()):
        ready = [tau for tau, av in pairs if av <= t]
        best_ready = max(ready) if ready else None
        out = []
        if best_ready is not None:
            out.append((best_ready, t))
        for tau, av in pairs:
            if av > t and (best_ready is None or tau > best_ready):
                out.append((tau, av))
        if out:
            buf[key] = tuple(out)
        else:
            del buf[key]


def propagate(store, edges, budget, t):
    """Найраніше прибуття в межах знімка.

    Кожен перехід мусить РОЗПОЧАТИСЯ в інтервалі [t, t + budget); момент прибуття
    може виходити за межу інтервалу, оскільки повідомлення фізично перебуває в дорозі.
    Ребра знімка вважаються сталими протягом усього інтервалу, тому обмеження на
    співвідношення затримки та кроку не потрібне.
    """
    adj = defaultdict(list)
    for u, v, w in edges:
        adj[u].append((v, w))
    new = {n: dict(b) for n, b in store.items()}
    end = t + budget
    for src, buf in store.items():
        if not buf:
            continue
        starts = defaultdict(list)          # момент відправлення -> ключі й tau
        for key, pairs in buf.items():
            for tau, av in pairs:
                dep = max(av, t)
                if dep < end:
                    starts[dep].append((key, tau))
        for t0, items in starts.items():
            arr = {src: t0}
            pq = [(t0, src)]
            while pq:
                a, u = heapq.heappop(pq)
                if a > arr.get(u, math.inf):
                    continue
                if max(a, t) >= end:        # відправитися в цьому кроці вже не можна
                    continue
                for v, w in adj[u]:
                    na = max(a, t) + w
                    if na < arr.get(v, math.inf):
                        arr[v] = na
                        heapq.heappush(pq, (na, v))
            for v, a in arr.items():
                if v == src:
                    continue
                for key, tau in items:
                    _add(new[v], key, tau, a)
    return new


def run(config, removed=(), spill=None, dt=None):
    dt = dt or PARAMS["dt"]
    times = list(range(0, T_END + 1, dt))
    nodes_all = [n for n in CONFIGS[config] if n not in removed]
    store = {n: {} for n in nodes_all}
    O, AGE, first_seen = {}, {}, {}
    dmax = {k: DMAX[k] * PARAMS["dmax_scale"] for k in ZONES}
    for t in times:
        act = [n for n in nodes_all if active(n, t, removed)]
        for n in nodes_all:
            if n not in act:
                store[n] = {}
        for n in act:
            ty = NODES[n]["type"]
            for k in sensing_at(t, n):
                _add(store[n], (k, ty), t, t)
        for n in act:
            _prune(store[n], t)
        sub = {n: store[n] for n in act}
        sub = propagate(sub, edges_at(t, act), dt, t)
        for n in act:
            store[n] = sub[n]
        cc = store["CC"]
        num, age = 0.0, {}
        for k in ZONES:
            best_q, freshest = 0.0, None
            for (kk, ty) in list(cc):
                if kk != k:
                    continue
                tau = _best(cc, (kk, ty), t)
                if tau is None:
                    continue
                freshest = tau if freshest is None else max(freshest, tau)
                if t - tau <= dmax[k]:
                    best_q = max(best_q, TYPES[ty]["q"] * PARAMS["q_scale"])
            num += W[k] * min(best_q, 1.0)
            age[k] = None if freshest is None else t - freshest
            if spill and k in spill and freshest is not None and freshest >= spill[k] and k not in first_seen:
                first_seen[k] = t
        O[t] = num / sum(W.values())
        AGE[t] = age
    return O, AGE, first_seen

def run_static(config, dt=None):
    """Базовий метод 1: статичний агрегований граф за вікном [t-Dmax, t]."""
    dt = dt or PARAMS["dt"]
    times = list(range(0, T_END + 1, dt))
    nodes_all = CONFIGS[config]
    dmax = {k: DMAX[k] * PARAMS["dmax_scale"] for k in ZONES}
    O = {}
    for t in times:
        num = 0.0
        for k in ZONES:
            win = [s for s in times if t - dmax[k] <= s <= t]
            adj = defaultdict(set); obs = {}
            for s in win:
                act = [n for n in nodes_all if active(n, s)]
                for u, v, _ in edges_at(s, act):
                    adj[u].add(v)
                for n in act:
                    if k in sensing_at(s, n):
                        obs[n] = max(obs.get(n, 0), TYPES[NODES[n]["type"]]["q"])
            reach = set()
            for src in obs:
                seen = {src}; stack = [src]
                while stack:
                    u = stack.pop()
                    for v in adj[u]:
                        if v not in seen:
                            seen.add(v); stack.append(v)
                if "CC" in seen:
                    reach.add(src)
            num += W[k] * max([obs[n] for n in reach], default=0.0)
        O[t] = num / sum(W.values())
    return O

def run_snapshot(config, dt=None):
    """Базовий метод 1: лише миттєва зв'язність знімка.

    Дані не переносяться між знімками; вимірювання зараховується, якщо встигає
    дійти до центру керування в межах того самого інтервалу [t, t + δ).
    """
    dt = dt or PARAMS["dt"]
    times = list(range(0, T_END + 1, dt))
    nodes_all = CONFIGS[config]
    O = {}
    for t in times:
        act = [n for n in nodes_all if active(n, t)]
        store = {n: {} for n in act}
        for n in act:
            ty = NODES[n]["type"]
            for k in sensing_at(t, n):
                _add(store[n], (k, ty), t, t)
        store = propagate(store, edges_at(t, act), dt, t)
        num = 0.0
        for k in ZONES:
            best = max([TYPES[ty]["q"] for (kk, ty) in store["CC"]
                        if kk == k and _best(store["CC"], (kk, ty), t + dt) is not None], default=0.0)
            num += W[k] * best
        O[t] = num / sum(W.values())
    return O

def run_nofreshness(config, dt=None):
    """Базовий метод 3: темпоральна досяжність без урахування віку й достовірності."""
    dt = dt or PARAMS["dt"]
    times = list(range(0, T_END + 1, dt))
    nodes_all = CONFIGS[config]
    store = {n: {} for n in nodes_all}
    O = {}
    for t in times:
        act = [n for n in nodes_all if active(n, t)]
        for n in nodes_all:
            if n not in act:
                store[n] = {}
        for n in act:
            for k in sensing_at(t, n):
                _add(store[n], (k, NODES[n]["type"]), t, t)
        sub = propagate({n: store[n] for n in act}, edges_at(t, act), dt, t)
        for n in act:
            store[n] = sub[n]
        seen = {kk for (kk, ty) in store["CC"] if _best(store["CC"], (kk, ty), t) is not None}
        O[t] = sum(W[k] for k in seen) / sum(W.values())
    return O

def spill_times():
    sp = {}
    for k in ZONES:
        r, c = (k - 1) // 4, (k - 1) % 4
        if r + c <= 2:
            sp[k] = 60 + 15 * (r + c)
    return sp

def mean(d, a=0, b=T_END):
    v = [x for t, x in d.items() if a <= t <= b]
    return sum(v) / len(v)

if __name__ == "__main__":
    SP = spill_times()
    print("=== показник і затримки виявлення ===")
    for cfg in "ABC":
        O, AGE, fs = run(cfg, spill=SP)
        det = {k: (fs[k] - SP[k] if k in fs else None) for k in sorted(SP)}
        mn = min(v for t, v in O.items() if t >= 5)
        print(f"{cfg}: штат {mean(O,5,55):.3f}  аварія {mean(O,60,115):.3f}  "
              f"після {mean(O,120,180):.3f}  min(5-180) {mn:.3f}  затримки {det}")
    print("\n=== базові методи (аварійний інтервал) ===")
    for cfg in "ABC":
        print(f"{cfg}: темпоральний {mean(run(cfg)[0],60,115):.3f}  "
              f"статичний {mean(run_static(cfg),60,115):.3f}  "
              f"знімок {mean(run_snapshot(cfg),60,115):.3f}  "
              f"без свіжості {mean(run_nofreshness(cfg),60,115):.3f}")
    print("\n=== критичність (C) ===")
    base = mean(run("C")[0])
    crit = sorted(((n, base - mean(run("C", removed=(n,))[0])) for n in CONFIGS["C"] if n != "CC"),
                  key=lambda x: -x[1])
    print(f"база {base:.3f}:", [(n, round(v, 3)) for n, v in crit])
