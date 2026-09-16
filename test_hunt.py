"""Tests pour hunt.py — le MOTEUR DE CHASSE unifié (le cœur de l'appli).

Unifie toutes les familles d'edge derrière UN harnais : registre de chasseurs →
chaque chasseur produit (strat_returns, bench_returns, n_trials, sr_variance, ...)
→ jugé par le CRITIC complet 4-gates → loggé en research_memory → leaderboard.
C'est ÇA l'appli : chasser des edges, les juger sans pitié, garder la trace.

Run: cd backend/edge_factory && ../../.venv/bin/python test_hunt.py
"""
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hunt  # noqa: E402


def _planted_edge():
    rng = random.Random(1)
    strat = [0.5 + rng.gauss(0, 0.3) for _ in range(300)]
    bench = [rng.gauss(0, 1) for _ in range(300)]
    return {"strat": strat, "bench": bench, "n_trials": 5, "sr_variance": 0.2}


def _pure_noise():
    rng = random.Random(2)
    strat = [rng.gauss(0, 1) for _ in range(300)]
    bench = [rng.gauss(0, 1) for _ in range(300)]
    return {"strat": strat, "bench": bench, "n_trials": 200, "sr_variance": 0.05}


def test_judge_reports_the_gates_that_ran():
    # Un chasseur sans pbo_matrix ni permutation n'est juge que par 3 gates : le resultat
    # (et donc le leaderboard / la memoire) doit le dire, pas afficher « 5-gates ».
    reg = hunt.Registry()
    reg.register("planted", _planted_edge)
    res = reg.judge("planted")
    assert res["gates_applied"] == ["beta_neutral", "dsr", "convexity"]


def _hourly(mean, seed, n=1440):
    rng = random.Random(seed)
    return lambda: {"strat": [mean + rng.gauss(0, 0.1) for _ in range(n)],
                    "bench": [random.Random(seed + 1000 + i).gauss(0, 1) for i in range(n)],
                    "n_trials": 1, "sr_variance": 0.05}


def test_hunt_all_deflates_with_the_measured_variance_of_the_trials():
    # Les chasseurs passaient sr_variance=0.05 en dur. Sur des barres horaires, le Sharpe
    # par barre vit autour de 0.0-0.2 : Var=0.05 place la barre DSR a SR0=0.35 par barre,
    # infranchissable. Mesure sur la vraie chasse 16/09 : DSR=0.00 pour les 10 familles.
    # Le DSR (Bailey & Lopez de Prado) deflate par la variance des Sharpe DES ESSAIS.
    reg = hunt.Registry()
    reg.register("planted_hourly", _hourly(0.02, 1))       # Sharpe/barre ~0.2
    for i in range(9):
        reg.register(f"noise_{i}", _hourly(0.0, 10 + i))
    reg.hunt_all()
    lb = {r["name"]: r for r in reg.leaderboard()}
    assert lb["planted_hourly"]["pass"] is True, lb["planted_hourly"]
    assert not any(lb[f"noise_{i}"]["pass"] for i in range(9))
    assert lb["planted_hourly"]["gates"]["sr_variance"] < 0.05


def test_register_and_list():
    reg = hunt.Registry()
    reg.register("planted", _planted_edge)
    reg.register("noise", _pure_noise)
    assert set(reg.names()) == {"planted", "noise"}


def test_judge_planted_edge_passes():
    reg = hunt.Registry()
    reg.register("planted", _planted_edge)
    res = reg.judge("planted")
    assert res["pass"] is True, res
    assert "sharpe" in res["gates"]


def test_judge_noise_fails():
    reg = hunt.Registry()
    reg.register("noise", _pure_noise)
    res = reg.judge("noise")
    assert res["pass"] is False, res


def test_hunt_all_logs_to_memory(tmp_path=None):
    d = tmp_path or tempfile.mkdtemp()
    mem = os.path.join(str(d), "mem.json")
    reg = hunt.Registry(memory_path=mem)
    reg.register("planted", _planted_edge)
    reg.register("noise", _pure_noise)
    results = reg.hunt_all()
    assert len(results) == 2
    # research_memory contient les 2 verdicts (relecture via la classe)
    from research_memory import ResearchMemory
    log = ResearchMemory(mem).all()
    assert len(log) == 2


def test_leaderboard_ranks_survivors_first():
    reg = hunt.Registry()
    reg.register("planted", _planted_edge)
    reg.register("noise", _pure_noise)
    reg.hunt_all()
    lb = reg.leaderboard()
    # le survivant (planted) doit être en tête
    assert lb[0]["name"] == "planted"
    assert lb[0]["pass"] is True


def test_judge_unknown_raises():
    reg = hunt.Registry()
    try:
        reg.judge("nope")
        assert False, "devrait lever"
    except KeyError:
        pass


def test_n_trials_reflects_total_registry_size():
    # V1 : le DSR doit déflater par le VRAI nombre d'essais = nb de hunters du
    # registre, pas le n_trials local d'une famille. Un hunter qui déclare n_trials=1
    # mais enregistré parmi 10 doit être jugé avec n_trials >= 10.
    reg = hunt.Registry()
    captured = {}

    def spy_hunter():
        d = _planted_edge()
        d["n_trials"] = 1  # la famille déclare 1
        return d

    for i in range(10):
        reg.register(f"h{i}", spy_hunter)
    # on instrumente evaluate_edge via le gate DSR : effective_n_trials exposé
    res = reg.judge("h0")
    assert res["gates"]["effective_n_trials"] >= 10, res["gates"]


def test_n_trials_floor_uses_hunter_value_when_larger():
    # si une famille déclare une grille plus large que le nb de hunters, on garde le max
    reg = hunt.Registry()

    def big_grid():
        d = _planted_edge()
        d["n_trials"] = 50
        return d
    reg.register("solo", big_grid)
    res = reg.judge("solo")
    assert res["gates"]["effective_n_trials"] == 50, res["gates"]


def test_permutation_gate_propagated():
    # un chasseur qui fournit une permutation insignifiante -> gate permutation FAIL
    reg = hunt.Registry()

    def hunter():
        d = _planted_edge()
        d["permutation"] = {"p_value": 0.9, "significant": False}
        return d
    reg.register("perm_fail", hunter)
    res = reg.judge("perm_fail")
    assert res["pass"] is False
    assert "permutation" in res["reasons"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            fails += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:
            fails += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
