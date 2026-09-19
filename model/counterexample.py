"""
Counterexample: a fully stationary network in which the static aggregated graph
reports observability while no time-respecting path to the control centre exists.

Nodes: S (sensor in zone 1), R (relay), C (control centre). None of them moves.
Only link availability changes in time:

    t < 60 :  R -> C available,  S -> R unavailable  (sensor uplink blocked)
    t >= 60:  S -> R available,  R -> C unavailable  (relay backhaul lost)

The aggregated graph over any window spanning t = 60 contains both edges and
therefore a path S -> R -> C. No time-respecting path exists, because the second
hop is available only before the first one.

Usage: python src/counterexample.py
"""
DT, T_END = 5, 120
TIMES = list(range(0, T_END + 1, DT))
DMAX = 30          # допустимий вік даних, хв
SWITCH = 60        # момент перемикання доступності каналів

def edges_at(t):
    """орієнтовані ребра знімка (u, v)"""
    return [("R", "C")] if t < SWITCH else [("S", "R")]

def sensing_at(t):
    """давач S спостерігає зону 1 у кожен момент"""
    return {"S"}

def temporal():
    """запропонований підхід: store-carry-forward уздовж часово-узгоджених шляхів"""
    buf = {n: None for n in "SRC"}        # момент найсвіжішого відомого вимірювання
    out = {}
    for t in TIMES:
        for n in sensing_at(t):
            buf[n] = t
        snapshot = dict(buf)
        for u, v in edges_at(t):
            if snapshot[u] is not None:
                buf[v] = max(buf[v] or -1, snapshot[u])
        out[t] = 1.0 if (buf["C"] is not None and t - buf["C"] <= DMAX) else 0.0
    return out

def static_aggregated():
    """базовий метод: агрегування ребер вікна зі збереженням орієнтації"""
    out = {}
    for t in TIMES:
        win = [s for s in TIMES if t - DMAX <= s <= t]
        adj = {}
        observers = set()
        for s in win:
            for u, v in edges_at(s):
                adj.setdefault(u, set()).add(v)
            observers |= sensing_at(s)
        reach = False
        for src in observers:
            seen, stack = {src}, [src]
            while stack:
                u = stack.pop()
                for v in adj.get(u, ()):
                    if v not in seen:
                        seen.add(v); stack.append(v)
            if "C" in seen:
                reach = True
        out[t] = 1.0 if reach else 0.0
    return out

if __name__ == "__main__":
    T, S = temporal(), static_aggregated()
    print(" t   запропонований   статичний")
    for t in TIMES:
        mark = "   <-- розбіжність" if S[t] > T[t] else ""
        print(f"{t:3d}      {T[t]:.0f}              {S[t]:.0f}{mark}")
    diff = [t for t in TIMES if S[t] > T[t]]
    print(f"\nкроків із завищенням: {len(diff)} з {len(TIMES)}")
    print(f"середнє: запропонований {sum(T.values())/len(T):.3f}, "
          f"статичний {sum(S.values())/len(S):.3f}")
    print("усі вузли нерухомі; змінюється лише доступність каналів у часі")
