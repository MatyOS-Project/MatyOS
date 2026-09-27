"""Stoqos — a calibrated model for the REALISTIC level.

MatyOS's three-valued logic has TRUE (the kernel proved it), FALSE (a
counterexample killed it) and REALISTIC (held on the evidence, but unproven).
TRUE and FALSE are decided by proof and by counterexample; only REALISTIC is
inherently uncertain. **Stoqos estimates that uncertainty** — given a bound that
survived the evidence, it outputs a *calibrated probability that the bound is
actually true* (would survive a proof / a harder world).

Honesty invariants, enforced here and never to be relaxed:

* Stoqos is **advisory only**. It grades a REALISTIC claim; it can never promote
  one to TRUE (the kernel's job) or demote to FALSE (a counterexample's job).
* **No leakage.** Features are read from the *weak* battery (the canonical sample
  a bound was surfaced on). The *label* — did it actually hold up — comes from a
  separate, harder battery. The model never sees the answer as an input.
* **Calibration is the product.** ``calibration_report`` measures whether "0.9"
  really means ~90%. A confident, miscalibrated score is worse than none.
* **Domain-bounded.** This baseline is validated only on graph-invariant
  inequalities. Outside that, callers should treat its output as unknown.

Pure Python, zero new dependencies — logistic regression by full-batch gradient
descent, standardised features, L2, balanced class weights.
"""
from __future__ import annotations

import json
import math
import os
import random
from dataclasses import dataclass, field
from itertools import combinations

from matyos.discovery import graph as G

FEATURES = [
    "tight_ratio",    # fraction of the sample where equality held (a tight bound)
    "mean_margin",    # average normalised slack  (vb - va)/(|vb|+1)
    "min_margin",     # smallest normalised slack
    "margin_cv",      # coefficient of variation of the raw slack
    "corr_ab",        # how coupled the two quantities are across the sample
    "spread_a",       # how much a(G) varies across the sample
    "spread_b",       # how much b(G) varies across the sample
]

_WEIGHTS_FILE = os.path.join(os.path.dirname(__file__), "stoqos_weights.json")


# --------------------------------------------------------------------------- #
# small statistics helpers (pure python)
# --------------------------------------------------------------------------- #
def _mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs):
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _corr(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return num / (dx * dy) if dx > 0 and dy > 0 else 0.0


# --------------------------------------------------------------------------- #
# features for one candidate bound  a(G) <= b(G)
# --------------------------------------------------------------------------- #
def features_from_values(va: list[float], vb: list[float]) -> dict:
    """Feature dict for a bound, from its two invariant value-lists on a battery.

    Assumes the bound holds on this battery (va <= vb); that is how candidates are
    surfaced. Reads only these values — never whether it holds elsewhere.
    """
    margins = [y - x for x, y in zip(va, vb)]
    norm = [m / (abs(y) + 1.0) for m, y in zip(margins, vb)]
    tight = sum(1 for m in margins if abs(m) < 1e-9) / len(margins)
    return {
        "tight_ratio": tight,
        "mean_margin": _mean(norm),
        "min_margin": min(norm) if norm else 0.0,
        "margin_cv": (_std(margins) / (_mean(margins) + 1e-9)) if margins else 0.0,
        "corr_ab": _corr(va, vb),
        "spread_a": _std(va) / (_mean([abs(v) for v in va]) + 1.0),
        "spread_b": _std(vb) / (_mean([abs(v) for v in vb]) + 1.0),
    }


def _vec(feats: dict) -> list[float]:
    return [float(feats[k]) for k in FEATURES]


# --------------------------------------------------------------------------- #
# richer feature set for the learned MLP (Phase 1)
# --------------------------------------------------------------------------- #
FEATURES_RICH = [
    "tight_ratio", "strict_ratio", "mean_margin", "min_margin", "max_margin",
    "q25_margin", "q75_margin", "margin_cv", "corr_ab", "spearman_ab",
    "spread_a", "spread_b", "mean_ratio",
]


def _quantile(xs, q):
    if not xs:
        return 0.0
    s = sorted(xs)
    i = min(len(s) - 1, int(q * (len(s) - 1) + 0.5))
    return s[i]


def _spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r
    return _corr(ranks(xs), ranks(ys))


def rich_features_from_values(va: list[float], vb: list[float]) -> dict:
    """A larger evidence description for a bound; the MLP learns to combine these."""
    margins = [y - x for x, y in zip(va, vb)]
    norm = [m / (abs(y) + 1.0) for m, y in zip(margins, vb)]
    n = len(margins)
    return {
        "tight_ratio": sum(1 for m in margins if abs(m) < 1e-9) / n,
        "strict_ratio": sum(1 for m in margins if m > 1e-9) / n,
        "mean_margin": _mean(norm),
        "min_margin": min(norm) if norm else 0.0,
        "max_margin": max(norm) if norm else 0.0,
        "q25_margin": _quantile(norm, 0.25),
        "q75_margin": _quantile(norm, 0.75),
        "margin_cv": (_std(margins) / (_mean(margins) + 1e-9)) if margins else 0.0,
        "corr_ab": _corr(va, vb),
        "spearman_ab": _spearman(va, vb),
        "spread_a": _std(va) / (_mean([abs(v) for v in va]) + 1.0),
        "spread_b": _std(vb) / (_mean([abs(v) for v in vb]) + 1.0),
        "mean_ratio": _mean(va) / (_mean(vb) + 1.0),
    }


def _vec_rich(feats: dict) -> list[float]:
    return [float(feats[k]) for k in FEATURES_RICH]


# --------------------------------------------------------------------------- #
# Phase 2: invariant metadata — WHAT the invariants are, not just how they behave.
# family, monotonicity under edge-addition (+1 up / -1 down / 0 none), and whether
# the quantity is a cardinality (extensive) or bounded (intensive).
# --------------------------------------------------------------------------- #
_FAMILY = {
    "min_degree": "deg", "max_degree": "deg", "avg_degree": "deg", "degeneracy": "deg",
    "diameter": "dist", "radius": "dist", "average_distance": "dist",
    "average_eccentricity": "dist", "girth": "dist",
    "vertex_connectivity": "conn", "edge_connectivity": "conn",
    "independence_number": "cov", "clique_number": "cov", "chromatic_number": "cov",
    "vertex_cover_number": "cov", "domination_number": "cov", "matching_number": "cov",
    "total_domination_number": "cov", "edge_cover_number": "cov",
    "order": "count", "size": "count", "triangles": "count",
    "spectral_radius": "spec", "energy": "spec", "algebraic_connectivity": "spec",
    "laplacian_spectral_radius": "spec",
}
_MONO = {  # sign of change when an edge is added
    "order": 0, "size": 1, "triangles": 1,
    "min_degree": 1, "max_degree": 1, "avg_degree": 1, "degeneracy": 1,
    "diameter": -1, "radius": -1, "average_distance": -1, "average_eccentricity": -1,
    "girth": -1, "vertex_connectivity": 1, "edge_connectivity": 1,
    "independence_number": -1, "clique_number": 1, "chromatic_number": 1,
    "vertex_cover_number": 1, "domination_number": -1, "matching_number": 1,
    "total_domination_number": -1, "edge_cover_number": -1,
    "spectral_radius": 1, "energy": 1, "algebraic_connectivity": 1,
    "laplacian_spectral_radius": 1,
}
_EXTENSIVE = {  # a cardinality that can grow ~n  (vs a bounded/intensive quantity)
    "order", "size", "triangles", "independence_number", "clique_number",
    "chromatic_number", "vertex_cover_number", "domination_number", "matching_number",
    "total_domination_number", "edge_cover_number",
}

FEATURES_META = ["mono_a", "mono_b", "mono_match", "same_family",
                 "ext_a", "ext_b", "known_rel"]
FEATURES_V2 = FEATURES_RICH + FEATURES_META


def meta_features(a: str, b: str) -> dict:
    """Structural metadata about the pair (a, b), independent of any battery."""
    ma, mb = _MONO.get(a, 0), _MONO.get(b, 0)
    from matyos.discovery import known
    status = known.classify(f"{a} <= {b}")["status"]
    return {
        "mono_a": float(ma), "mono_b": float(mb),
        "mono_match": 1.0 if (ma and ma == mb) else (-1.0 if ma * mb < 0 else 0.0),
        "same_family": 1.0 if _FAMILY.get(a) == _FAMILY.get(b) else 0.0,
        "ext_a": 1.0 if a in _EXTENSIVE else 0.0,
        "ext_b": 1.0 if b in _EXTENSIVE else 0.0,
        "known_rel": 1.0 if status in ("known", "derived") else 0.0,
    }


def features_v2(a: str, b: str, va: list[float], vb: list[float]) -> dict:
    """The full Phase-2 feature dict: evidence (rich) + invariant metadata. A
    superset — every model reads only the keys it was trained on."""
    return {**rich_features_from_values(va, vb), **meta_features(a, b)}


# --------------------------------------------------------------------------- #
# the model
# --------------------------------------------------------------------------- #
@dataclass
class Stoqos:
    w: list[float] = field(default_factory=lambda: [0.0] * len(FEATURES))
    b: float = 0.0
    mean_: list[float] = field(default_factory=lambda: [0.0] * len(FEATURES))
    std_: list[float] = field(default_factory=lambda: [1.0] * len(FEATURES))
    trained: bool = False

    # ---- fit / predict ---------------------------------------------------- #
    def fit(self, X: list[list[float]], y: list[int], *,
            iters: int = 6000, lr: float = 0.3, l2: float = 1e-3) -> "Stoqos":
        n, d = len(X), len(FEATURES)
        self.mean_ = [_mean([row[k] for row in X]) for k in range(d)]
        self.std_ = [(_std([row[k] for row in X]) or 1.0) for k in range(d)]
        Xs = [[(row[k] - self.mean_[k]) / self.std_[k] for k in range(d)] for row in X]
        npos = sum(y) or 1
        nneg = (n - sum(y)) or 1
        wpos, wneg = n / (2 * npos), n / (2 * nneg)      # balanced classes
        self.w = [0.0] * d
        self.b = 0.0
        for _ in range(iters):
            gw = [0.0] * d
            gb = 0.0
            for xi, yi in zip(Xs, y):
                z = self.b + sum(self.w[k] * xi[k] for k in range(d))
                p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
                err = (p - yi) * (wpos if yi else wneg)
                for k in range(d):
                    gw[k] += err * xi[k]
                gb += err
            for k in range(d):
                self.w[k] -= lr * (gw[k] / n + l2 * self.w[k])
            self.b -= lr * (gb / n)
        self.trained = True
        return self

    def predict_proba(self, feats: dict) -> float:
        x = _vec(feats)
        z = self.b + sum(self.w[k] * (x[k] - self.mean_[k]) / self.std_[k]
                         for k in range(len(FEATURES)))
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))

    # ---- persistence ------------------------------------------------------ #
    def to_dict(self) -> dict:
        return {"features": FEATURES, "w": self.w, "b": self.b,
                "mean": self.mean_, "std": self.std_, "trained": self.trained}

    @classmethod
    def from_dict(cls, d: dict) -> "Stoqos":
        return cls(w=d["w"], b=d["b"], mean_=d["mean"], std_=d["std"],
                   trained=d.get("trained", True))

    def save(self, path: str = _WEIGHTS_FILE) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def default(cls) -> "Stoqos | None":
        """Load the shipped pre-trained model, or None if it isn't present."""
        try:
            with open(_WEIGHTS_FILE) as f:
                return cls.from_dict(json.load(f))
        except (OSError, ValueError, KeyError):
            return None


_MLP_FILE = os.path.join(os.path.dirname(__file__), "stoqos_mlp.json")


def _sigmoid(z):
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


@dataclass
class StoqosNet:
    """A small pure-Python MLP over the rich feature set — the Phase-1 encoder.

    One hidden ReLU layer, sigmoid output, trained by mini-batch SGD with L2, then
    temperature-scaled for calibration. Same contract as Stoqos: a probability in
    [0, 1], never a verdict.
    """
    W1: list = field(default_factory=list)   # H x D
    b1: list = field(default_factory=list)   # H
    W2: list = field(default_factory=list)   # H
    b2: float = 0.0
    mean_: list = field(default_factory=list)
    std_: list = field(default_factory=list)
    T: float = 1.0                            # temperature (calibration)
    features: list = field(default_factory=lambda: list(FEATURES_RICH))
    trained: bool = False

    def _std_vec(self, feats):
        x = [float(feats[k]) for k in self.features]
        return [(x[k] - self.mean_[k]) / self.std_[k] for k in range(len(x))]

    def _forward(self, xs):
        H = len(self.W1)
        pre = [sum(self.W1[j][k] * xs[k] for k in range(len(xs))) + self.b1[j]
               for j in range(H)]
        h = [p if p > 0 else 0.0 for p in pre]           # ReLU
        z = sum(self.W2[j] * h[j] for j in range(H)) + self.b2
        return pre, h, z

    def predict_logit(self, feats):
        return self._forward(self._std_vec(feats))[2]

    def predict_proba(self, feats):
        return _sigmoid(self.predict_logit(feats) / self.T)

    def fit(self, X_feats, y, *, features=None, hidden=16, epochs=60, lr=0.05,
            l2=1e-4, batch=64, seed=0):
        if features is not None:
            self.features = list(features)
        rng = random.Random(seed)
        X = [[float(f[k]) for k in self.features] for f in X_feats]
        n, d = len(X), len(self.features)
        self.mean_ = [_mean([row[k] for row in X]) for k in range(d)]
        self.std_ = [(_std([row[k] for row in X]) or 1.0) for k in range(d)]
        Xs = [[(row[k] - self.mean_[k]) / self.std_[k] for k in range(d)] for row in X]
        H = hidden
        scale = 1.0 / math.sqrt(d)
        self.W1 = [[rng.gauss(0, scale) for _ in range(d)] for _ in range(H)]
        self.b1 = [0.0] * H
        self.W2 = [rng.gauss(0, 1.0 / math.sqrt(H)) for _ in range(H)]
        self.b2 = 0.0
        npos = sum(y) or 1
        nneg = (n - sum(y)) or 1
        wpos, wneg = n / (2 * npos), n / (2 * nneg)
        idx = list(range(n))
        for _ in range(epochs):
            rng.shuffle(idx)
            for s in range(0, n, batch):
                bi = idx[s:s + batch]
                gW1 = [[0.0] * d for _ in range(H)]
                gb1 = [0.0] * H
                gW2 = [0.0] * H
                gb2 = 0.0
                for i in bi:
                    xs = Xs[i]
                    pre, h, z = self._forward(xs)
                    p = _sigmoid(z)
                    cw = wpos if y[i] else wneg
                    dz = (p - y[i]) * cw
                    for j in range(H):
                        gW2[j] += dz * h[j]
                        dh = dz * self.W2[j]
                        dpre = dh if pre[j] > 0 else 0.0
                        for k in range(d):
                            gW1[j][k] += dpre * xs[k]
                        gb1[j] += dpre
                    gb2 += dz
                m = len(bi)
                for j in range(H):
                    self.W2[j] -= lr * (gW2[j] / m + l2 * self.W2[j])
                    self.b1[j] -= lr * (gb1[j] / m)
                    for k in range(d):
                        self.W1[j][k] -= lr * (gW1[j][k] / m + l2 * self.W1[j][k])
                self.b2 -= lr * (gb2 / m)
        self.trained = True
        return self

    def calibrate(self, X_feats, y):
        """Fit the temperature T (1-D search) to minimise log-loss on held-out data."""
        logits = [self.predict_logit(f) for f in X_feats]
        best_T, best_ll = 1.0, 1e18
        T = 0.4
        while T <= 4.0:
            ll = 0.0
            for zi, yi in zip(logits, y):
                p = min(1 - 1e-12, max(1e-12, _sigmoid(zi / T)))
                ll += -(yi * math.log(p) + (1 - yi) * math.log(1 - p))
            if ll < best_ll:
                best_ll, best_T = ll, T
            T += 0.05
        self.T = best_T
        return self

    def to_dict(self):
        return {"kind": "mlp", "features": self.features, "W1": self.W1,
                "b1": self.b1, "W2": self.W2, "b2": self.b2, "mean": self.mean_,
                "std": self.std_, "T": self.T, "trained": self.trained}

    @classmethod
    def from_dict(cls, d):
        return cls(W1=d["W1"], b1=d["b1"], W2=d["W2"], b2=d["b2"], mean_=d["mean"],
                   std_=d["std"], T=d.get("T", 1.0),
                   features=d.get("features", list(FEATURES_RICH)),
                   trained=d.get("trained", True))

    def save(self, path=_MLP_FILE):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f)

    @classmethod
    def default_mlp(cls):
        try:
            with open(_MLP_FILE) as f:
                return cls.from_dict(json.load(f))
        except (OSError, ValueError, KeyError):
            return None


# --------------------------------------------------------------------------- #
# calibration + evaluation
# --------------------------------------------------------------------------- #
def brier(model: Stoqos, X_feats: list[dict], y: list[int]) -> float:
    return _mean([(model.predict_proba(f) - yi) ** 2 for f, yi in zip(X_feats, y)])


def log_loss(model: Stoqos, X_feats: list[dict], y: list[int]) -> float:
    tot = 0.0
    for f, yi in zip(X_feats, y):
        p = min(1 - 1e-12, max(1e-12, model.predict_proba(f)))
        tot += -(yi * math.log(p) + (1 - yi) * math.log(1 - p))
    return tot / len(y)


def selective_report(model, X_feats, y, thresholds=(0.0, 0.2, 0.4, 0.6, 0.8)) -> list:
    """Accuracy/coverage tradeoff of abstention. Commitment = 2*|p-0.5| (how far
    from a coin-flip). For each minimum commitment, report the fraction we still
    answer (coverage) and how good those answers are (accuracy, Brier). A good
    model gets more accurate as it abstains more — that is the honest guarantee."""
    preds = [model.predict_proba(f) for f in X_feats]
    rows = []
    for t in thresholds:
        idx = [i for i in range(len(preds)) if abs(preds[i] - 0.5) * 2 >= t]
        if not idx:
            continue
        acc = sum(1 for i in idx if round(preds[i]) == y[i]) / len(idx)
        br = sum((preds[i] - y[i]) ** 2 for i in idx) / len(idx)
        rows.append({"min_commit": t, "coverage": round(len(idx) / len(preds), 3),
                     "accuracy": round(acc, 3), "brier": round(br, 4)})
    return rows


def calibration_report(model: Stoqos, X_feats: list[dict], y: list[int],
                       bins: int = 5) -> list[dict]:
    """Reliability table: for each probability bin, predicted vs empirical rate."""
    buckets = [[] for _ in range(bins)]
    for f, yi in zip(X_feats, y):
        p = model.predict_proba(f)
        idx = min(bins - 1, int(p * bins))
        buckets[idx].append((p, yi))
    rows = []
    for i, bkt in enumerate(buckets):
        if not bkt:
            continue
        rows.append({"bin": f"{i/bins:.1f}-{(i+1)/bins:.1f}", "n": len(bkt),
                     "pred": round(_mean([p for p, _ in bkt]), 3),
                     "actual": round(_mean([yi for _, yi in bkt]), 3)})
    return rows


# --------------------------------------------------------------------------- #
# grounded dataset: weak battery = features, harder battery = labels
# --------------------------------------------------------------------------- #
def _rand_connected(n: int, rng: random.Random, extra_p: float = 0.22) -> "G.Graph":
    order = list(range(n))
    rng.shuffle(order)
    edges = set()
    for i in range(1, n):                       # random spanning tree -> connected
        j = rng.randrange(0, i)
        edges.add(tuple(sorted((order[i], order[j]))))
    for a, b in combinations(range(n), 2):
        if (a, b) not in edges and rng.random() < extra_p:
            edges.add((a, b))
    return G.Graph.of(n, list(edges), f"rand{n}")


def strong_battery(seed: int = 17, per_n: int = 22, n_lo: int = 5, n_hi: int = 10):
    """The harder world: the canonical sample plus seeded random connected graphs."""
    rng = random.Random(seed)
    gs = list(G.sample_graphs())
    for n in range(n_lo, n_hi + 1):
        for _ in range(per_n):
            g = _rand_connected(n, rng)
            if G.is_connected(g):
                gs.append(g)
    return gs


def weak_battery(rng: random.Random, size: int = 10,
                 n_lo: int = 4, n_hi: int = 8):
    """A small random sample — *weak evidence*. A bound holding here is only a
    REALISTIC candidate: it may still be false in the wider world."""
    gs = []
    while len(gs) < size:
        g = _rand_connected(rng.randint(n_lo, n_hi), rng)
        if G.is_connected(g):
            gs.append(g)
    return gs


def weak_infer_battery(seed: int = 0, size: int = 16):
    """A fixed weak battery for scoring at inference, drawn from the same
    distribution the model was trained on (so its calibration transfers)."""
    return weak_battery(random.Random(seed), size=size)


def build_dataset(strong=None, invariants=None, *, n_batteries: int = 40,
                  weak_size: int = 10, seed: int = 17, feat_fn=features_from_values,
                  with_meta: bool = False):
    """Return (X_feats, y, pairs) from many weak-evidence episodes.

    For each of ``n_batteries`` small random *weak* batteries: every non-identity
    bound ``a(G) <= b(G)`` that holds on it is a REALISTIC candidate. Its features
    are read from that weak battery; its label is 1 if the bound also holds on the
    hard *strong* battery (robustly true) and 0 if the strong battery refutes it
    (looked realistic on thin evidence, actually false). The same pair can appear
    under different weak batteries — different evidence, possibly different label —
    which is exactly what teaches Stoqos to read the evidence, not memorise pairs.
    """
    strong = strong or strong_battery(seed=seed + 1)
    inv = invariants or G.all_invariants()
    names = list(inv)
    eps = 1e-9
    vsg = {k: [float(inv[k](g)) for g in strong] for k in names}
    rng = random.Random(seed)
    X, y, pairs = [], [], []
    for _ in range(n_batteries):
        weak = weak_battery(rng, size=weak_size)
        vw = {k: [float(inv[k](g)) for g in weak] for k in names}
        for a in names:
            for b in names:
                if a == b:
                    continue
                va, vb = vw[a], vw[b]
                if not all(x <= yv + eps for x, yv in zip(va, vb)):
                    continue                    # fails even on weak evidence
                if all(abs(x - yv) < eps for x, yv in zip(va, vb)):
                    continue                    # an identity, not a bound
                sa, sb = vsg[a], vsg[b]
                holds_strong = all(x <= yv + eps for x, yv in zip(sa, sb))
                X.append(features_v2(a, b, va, vb) if with_meta else feat_fn(va, vb))
                y.append(1 if holds_strong else 0)
                pairs.append(f"{a} <= {b}")
    return X, y, pairs


def train_default(seed: int = 17, save: bool = True):
    """Build the grounded dataset, fit Stoqos, evaluate calibration, optionally
    save the weights. Returns (model, metrics)."""
    X, y, pairs = build_dataset(strong=strong_battery(seed=seed))
    # deterministic split by index parity keeps it dependency-free and reproducible
    tr = [i for i in range(len(X)) if i % 3 != 0]
    te = [i for i in range(len(X)) if i % 3 == 0]
    Xtr = [_vec(X[i]) for i in tr]
    ytr = [y[i] for i in tr]
    model = Stoqos().fit(Xtr, ytr)
    Xte_f = [X[i] for i in te] or X
    yte = [y[i] for i in te] or y
    metrics = {
        "n_total": len(X), "n_pos": sum(y), "n_neg": len(y) - sum(y),
        "brier_test": round(brier(model, Xte_f, yte), 4),
        "log_loss_test": round(log_loss(model, Xte_f, yte), 4),
        "reliability": calibration_report(model, Xte_f, yte),
        "weights": {k: round(w, 3) for k, w in zip(FEATURES, model.w)},
    }
    if save:
        model.save()
    return model, metrics


def train_mlp_default(seed: int = 17, n_batteries: int = 55, save: bool = True):
    """Phase 1: train the MLP encoder, calibrate it, and compare it head-to-head
    against the logistic baseline on FRESH data neither model trained on."""
    strong = strong_battery(seed=seed + 1)
    Xr, y, _ = build_dataset(strong=strong, n_batteries=n_batteries, seed=seed,
                             feat_fn=rich_features_from_values)
    tr = [i for i in range(len(Xr)) if i % 5 in (0, 1, 2)]
    va = [i for i in range(len(Xr)) if i % 5 == 3]
    net = StoqosNet().fit([Xr[i] for i in tr], [y[i] for i in tr],
                          hidden=12, epochs=100, lr=0.12, seed=seed)
    net.calibrate([Xr[i] for i in va], [y[i] for i in va])

    # honest evaluation: a fresh unseen seed, row-aligned for both models
    hstrong = strong_battery(seed=100, per_n=12)
    Xr_h, yh, _ = build_dataset(strong=hstrong, n_batteries=22, seed=99,
                                feat_fn=rich_features_from_values)
    X7_h, yh2, _ = build_dataset(strong=hstrong, n_batteries=22, seed=99,
                                 feat_fn=features_from_values)   # same rows, 7 feats
    base = Stoqos.default() or Stoqos()
    metrics = {
        "held_out_n": len(Xr_h), "n_pos": sum(yh), "n_neg": len(yh) - sum(yh),
        "mlp_brier": round(brier(net, Xr_h, yh), 4),
        "mlp_log_loss": round(log_loss(net, Xr_h, yh), 4),
        "baseline_brier": round(brier(base, X7_h, yh2), 4),
        "baseline_log_loss": round(log_loss(base, X7_h, yh2), 4),
        "temperature": round(net.T, 3),
        "mlp_reliability": calibration_report(net, Xr_h, yh),
    }
    metrics["won"] = metrics["mlp_brier"] < metrics["baseline_brier"]
    if save and metrics["won"]:
        net.save()
    return net, metrics


def train_v2_default(seed: int = 17, n_batteries: int = 55, save: bool = True):
    """Phase 2: train the MLP on evidence + invariant metadata, and compare it
    head-to-head against the Phase-1 (evidence-only) MLP on fresh unseen data."""
    strong = strong_battery(seed=seed + 1)
    X, y, _ = build_dataset(strong=strong, n_batteries=n_batteries, seed=seed,
                            with_meta=True)
    tr = [i for i in range(len(X)) if i % 5 in (0, 1, 2)]
    va = [i for i in range(len(X)) if i % 5 == 3]
    net = StoqosNet().fit([X[i] for i in tr], [y[i] for i in tr],
                          features=FEATURES_V2, hidden=12, epochs=100, lr=0.12,
                          seed=seed)
    net.calibrate([X[i] for i in va], [y[i] for i in va])

    hstrong = strong_battery(seed=100, per_n=12)
    Xh, yh, _ = build_dataset(strong=hstrong, n_batteries=22, seed=99, with_meta=True)
    prev = StoqosNet.default_mlp()          # the Phase-1 model (reads its own subset)
    metrics = {
        "held_out_n": len(Xh), "n_pos": sum(yh), "n_neg": len(yh) - sum(yh),
        "v2_brier": round(brier(net, Xh, yh), 4),
        "v2_log_loss": round(log_loss(net, Xh, yh), 4),
        "phase1_brier": round(brier(prev, Xh, yh), 4) if prev else None,
        "temperature": round(net.T, 3),
        "v2_reliability": calibration_report(net, Xh, yh),
    }
    metrics["won_vs_phase1"] = (prev is None or
                                metrics["v2_brier"] < metrics["phase1_brier"])
    if save and metrics["won_vs_phase1"]:
        net.save()
    return net, metrics


# --------------------------------------------------------------------------- #
# Phase 5: a domain-general evidence scorer. The evidence features (tightness,
# margins, correlation) describe ANY bound "a <= b" from two aligned value lists,
# with no graph-specific metadata — so a model trained on them can be applied to a
# different domain (e.g. number sequences). This is the test of real generality.
# --------------------------------------------------------------------------- #
_EVIDENCE_FILE = os.path.join(os.path.dirname(__file__), "stoqos_evidence.json")


def train_evidence_default(seed: int = 17, n_batteries: int = 55, save: bool = True):
    """Train the domain-general (evidence-only) MLP and save it separately."""
    X, y, _ = build_dataset(strong=strong_battery(seed=seed + 1),
                            n_batteries=n_batteries, seed=seed,
                            feat_fn=rich_features_from_values)
    tr = [i for i in range(len(X)) if i % 5 in (0, 1, 2)]
    va = [i for i in range(len(X)) if i % 5 == 3]
    net = StoqosNet().fit([X[i] for i in tr], [y[i] for i in tr],
                          features=FEATURES_RICH, hidden=12, epochs=100, lr=0.12,
                          seed=seed)
    net.calibrate([X[i] for i in va], [y[i] for i in va])
    if save:
        net.save(_EVIDENCE_FILE)
    return net


def evidence_model():
    """Load the domain-general evidence model, or None."""
    try:
        with open(_EVIDENCE_FILE) as f:
            return StoqosNet.from_dict(json.load(f))
    except (OSError, ValueError, KeyError):
        return None


def score_evidence(lhs_values, rhs_values, model=None) -> "float | None":
    """Domain-general REALISTIC score for a bound, from two aligned value lists
    (the left and right sides evaluated on the same evidence points). Works for
    any domain — graphs, sequences, anything — because it reads only evidence.
    Returns None if the bound fails on the evidence (then it is FALSE)."""
    model = model or evidence_model()
    if model is None or not lhs_values:
        return None
    if not all(x <= y + 1e-9 for x, y in zip(lhs_values, rhs_values)):
        return None
    return model.predict_proba(rich_features_from_values(list(lhs_values),
                                                         list(rhs_values)))


# --------------------------------------------------------------------------- #
# scoring a claim (advisory REALISTIC grade)
# --------------------------------------------------------------------------- #
def realistic_score(statement: str, model=None,
                    battery=None, invariants=None, samples: int = 6) -> float | None:
    """Calibrated probability that a REALISTIC graph-inequality bound is true.

    ``statement`` is "a <= b". Returns None if the model is unavailable, the
    invariants are unknown (out of domain), or the bound doesn't actually hold on
    the battery (then it is FALSE, not REALISTIC — not our call to make).
    """
    model = model or StoqosNet.default_mlp() or Stoqos.default()   # prefer the MLP
    if model is None or " <= " not in statement:
        return None
    a, b = (s.strip() for s in statement.split(" <= "))
    inv = invariants or G.all_invariants()
    if a not in inv or b not in inv:
        return None
    # Average over several independent evidence samples. A single small battery is
    # a noisy draw; averaging cuts the variance. If the bound fails on ANY sample,
    # a counterexample exists — it is FALSE, not REALISTIC, so we abstain.
    # features_v2 is the full superset (evidence + metadata); each model reads only
    # the keys it was trained on, so this serves logistic, Phase-1 and Phase-2 alike.
    batteries = [battery] if battery else [weak_infer_battery(seed=s, size=14)
                                           for s in range(samples)]
    probs = []
    for bat in batteries:
        va = [float(inv[a](g)) for g in bat]
        vb = [float(inv[b](g)) for g in bat]
        if not all(x <= y + 1e-9 for x, y in zip(va, vb)):
            return None                          # refuted by the evidence
        probs.append(model.predict_proba(features_v2(a, b, va, vb)))
    return sum(probs) / len(probs)


# --------------------------------------------------------------------------- #
# Phase 3: a Jev-shaped typed API — a decision, not prose. Abstains honestly.
# --------------------------------------------------------------------------- #
_COMMIT_TAU = 0.5   # abstain ("uncertain") when 2*|p-0.5| < this — too close to call


@dataclass(frozen=True)
class Judgement:
    """A typed verdict about a claim. Stoqos never asserts TRUE (that is the
    kernel's job); it returns REALISTIC with a calibrated probability, FALSE when
    the evidence gives a counterexample, UNCERTAIN when it isn't decisive enough
    to commit (Phase-4 abstention), or UNKNOWN when it cannot judge at all."""
    verdict: str                 # "realistic" | "uncertain" | "false" | "unknown"
    value: "float | None"        # calibrated P(true) when realistic, else None
    confidence: float            # 0..1, from agreement across evidence samples
    known: bool                  # matches a theorem already in the known-facts DB
    backend: str                 # model that produced it
    note: str


def judge(claim: str, model=None, samples: int = 6, invariants=None) -> Judgement:
    """Score one claim `a <= b` and return a typed Judgement (see :class:`Judgement`)."""
    model = model or StoqosNet.default_mlp() or Stoqos.default()
    backend = type(model).__name__ if model else "none"
    if model is None or " <= " not in claim:
        return Judgement("unknown", None, 0.0, False, backend,
                         "unparseable claim or no model available")
    a, b = (s.strip() for s in claim.split(" <= "))
    inv = invariants or G.all_invariants()
    if a not in inv or b not in inv:
        return Judgement("unknown", None, 0.0, False, backend,
                         "not both recognised graph invariants (out of domain)")
    known = meta_features(a, b)["known_rel"] == 1.0
    probs, fails = [], 0
    for s in range(samples):
        bat = weak_infer_battery(seed=s, size=14)
        va = [float(inv[a](g)) for g in bat]
        vb = [float(inv[b](g)) for g in bat]
        if not all(x <= y + 1e-9 for x, y in zip(va, vb)):
            fails += 1
            continue
        probs.append(model.predict_proba(features_v2(a, b, va, vb)))
    if fails:
        return Judgement("false", None, 1.0, known, backend,
                         f"counterexample found on {fails}/{samples} evidence samples")
    val = sum(probs) / len(probs)
    conf = max(0.0, min(1.0, 1.0 - 2.0 * _std(probs)))   # samples agree -> confident
    commit = 2.0 * abs(val - 0.5)                         # how decisive (0..1)
    if commit < _COMMIT_TAU:                              # Phase-4 honest abstention
        return Judgement("uncertain", round(val, 4), round(conf, 3), known, backend,
                         "too close to call — abstaining rather than guessing")
    note = "matches a known theorem" if known else "held on all evidence; unproven"
    return Judgement("realistic", round(val, 4), round(conf, 3), known, backend, note)


def judge_batch(claims: list[str], model=None, samples: int = 6) -> list[Judgement]:
    model = model or StoqosNet.default_mlp() or Stoqos.default()
    return [judge(c, model=model, samples=samples) for c in claims]
