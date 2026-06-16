"""Tests known-answer pour _dsr_pbo.py — le cœur statistique du gate overfit.

Couvre les briques pures (pas le wiring IO main()) :
  - expected_max_sharpe : la pénalité multiple-testing (croît avec n_trials)
  - deflated_sharpe     : décroît quand n_trials monte (SR fixe)
  - pbo_cscv            : calibre ~0.5 sur du bruit pur (aucun edge)
  - moments / sharpe    : valeurs calculées à la main

Run: python -m pytest test_dsr_pbo.py -q   (modules flat at repo root)
"""
import math
import os
import random
import sys

from statistics import NormalDist

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _dsr_pbo as d  # noqa: E402

EULER = 0.5772156649015329
_N = NormalDist()


# --------------------------------------------------------------------------
# moments / sharpe — known-answer sur petits échantillons
# --------------------------------------------------------------------------
def test_sharpe_hand_computed():
    # [1,2,3] : mean=2, stdev(ddof=1)=1 -> Sharpe=2.0
    assert abs(d._sharpe([1, 2, 3]) - 2.0) < 1e-12


def test_sharpe_degenerate():
    assert d._sharpe([5]) == 0.0            # n<2
    assert d._sharpe([3, 3, 3]) == 0.0      # variance nulle


def test_skew_symmetric_is_zero():
    assert abs(d._skew([-2, -1, 0, 1, 2])) < 1e-12


def test_skew_hand_computed():
    # [1,2,4] : mu=7/3, m3/m2**1.5 calculé à la main
    xs = [1, 2, 4]
    mu = 7 / 3
    m2 = sum((x - mu) ** 2 for x in xs) / 3
    m3 = sum((x - mu) ** 3 for x in xs) / 3
    assert abs(d._skew(xs) - m3 / m2 ** 1.5) < 1e-12


def test_kurtosis_hand_computed():
    # [-2,-1,0,1,2] : m2=2, m4=6.8 -> kurt(non-excess)=6.8/4=1.7
    assert abs(d._kurtosis([-2, -1, 0, 1, 2]) - 1.7) < 1e-12


# --------------------------------------------------------------------------
# expected_max_sharpe — la pénalité multiple-testing
# --------------------------------------------------------------------------
def test_expected_max_sharpe_hand_computed():
    # n_trials=2, var=1 : formule fermée de Lopez de Prado
    expected = ((1 - EULER) * _N.inv_cdf(1 - 1.0 / 2)
                + EULER * _N.inv_cdf(1 - 1.0 / (2 * math.e)))
    assert abs(d.expected_max_sharpe(1.0, 2) - expected) < 1e-12


def test_expected_max_sharpe_grows_with_n_trials():
    # plus on teste de stratégies, plus le Sharpe-max attendu sous H0 monte
    a = d.expected_max_sharpe(1.0, 10)
    b = d.expected_max_sharpe(1.0, 100)
    c = d.expected_max_sharpe(1.0, 1000)
    assert a < b < c


def test_expected_max_sharpe_scales_with_sqrt_variance():
    # SR0 ∝ √Var(SR)
    base = d.expected_max_sharpe(1.0, 50)
    quad = d.expected_max_sharpe(4.0, 50)   # variance ×4 -> facteur 2
    assert abs(quad - 2 * base) < 1e-9


def test_expected_max_sharpe_degenerate():
    assert d.expected_max_sharpe(1.0, 1) == 0.0      # n_trials<2
    assert d.expected_max_sharpe(0.0, 100) == 0.0    # variance nulle


# --------------------------------------------------------------------------
# deflated_sharpe / psr
# --------------------------------------------------------------------------
def test_psr_equals_half_at_benchmark():
    # SR == benchmark -> P(SR_vrai > benchmark) = 0.5
    assert abs(d.psr(1.0, 1.0, 250, 0.0, 3.0) - 0.5) < 1e-12


def test_deflated_sharpe_decreases_as_n_trials_rises():
    # même Sharpe, mais plus d'essais -> DSR s'effondre (déflation honnête)
    kw = dict(T=250, skew=0.0, kurt=3.0, sr_variance=0.25)
    few = d.deflated_sharpe(1.0, n_trials=2, **kw)
    many = d.deflated_sharpe(1.0, n_trials=100000, **kw)
    assert few > many
    assert many < 0.05


# --------------------------------------------------------------------------
# pbo_cscv — calibration sur bruit pur
# --------------------------------------------------------------------------
def test_pbo_calibrates_near_half_on_pure_noise():
    # aucun edge (returns i.i.d. gaussiens) -> la meilleure strat IS n'a aucune
    # raison d'être bonne OOS : PBO moyen ≈ 0.5 (on moyenne sur des seeds car un
    # tirage unique est bruité).
    vals = []
    for seed in range(40):
        rng = random.Random(seed)
        mat = [[rng.gauss(0, 1) for _ in range(10)] for _ in range(120)]
        pbo, _ = d.pbo_cscv(mat, S=8)
        vals.append(pbo)
    avg = sum(vals) / len(vals)
    assert 0.35 < avg < 0.65, avg


def test_pbo_combos_count():
    # S=8 -> C(8,4)=70 combinaisons IS/OOS
    rng = random.Random(1)
    mat = [[rng.gauss(0, 1) for _ in range(6)] for _ in range(96)]
    _, logits = d.pbo_cscv(mat, S=8)
    assert len(logits) == math.comb(8, 4)


def test_pbo_degenerate_returns_nan():
    pbo, logits = d.pbo_cscv([[1.0, 2.0]], S=16)   # T<S
    assert math.isnan(pbo)
    assert logits == []
    pbo2, _ = d.pbo_cscv([[1.0]] * 40, S=16)        # N<2
    assert math.isnan(pbo2)


if __name__ == "__main__":
    fns = [val for k, val in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
