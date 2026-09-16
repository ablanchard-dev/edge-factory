#!/usr/bin/env python3
"""Moteur de chasse à l'edge UNIFIÉ — le cœur de l'appli Alpha-Forge.

Le but de l'appli : CHASSER des edges/stratégies, les juger sans pitié, garder la
trace. Ce module unifie toutes les familles éparpillées (momentum, cross-sectional,
funding, hawkes, transfer-entropy, liq-spike…) derrière UN registre + UN harnais :

  Registry.register(nom, hunter)   # hunter() → dict d'inputs CRITIC
  Registry.judge(nom)              # → verdict 4-gates + log research_memory
  Registry.hunt_all()             # juge tous les chasseurs
  Registry.leaderboard()          # classe : survivants d'abord, par Sharpe

Un "hunter" est une callable sans argument qui retourne un dict :
  {strat, bench, n_trials, sr_variance, [pbo_matrix], [permutation]}
(les familles existantes produisent déjà ces returns ; un hunter = l'adaptateur
fetch+backtest → ces séries). Le CRITIC (verdict.evaluate_edge) reste l'arbitre.
"""
import statistics
from typing import Callable, Dict, List, Optional

from _dsr_pbo import _sharpe
from research_memory import ResearchMemory
from verdict import evaluate_edge

Hunter = Callable[[], Dict]


class Registry:
    def __init__(self, memory_path: Optional[str] = None):
        self._hunters: Dict[str, Hunter] = {}
        self._memory = ResearchMemory(memory_path) if memory_path else None
        self._results: Dict[str, Dict] = {}

    def register(self, name: str, hunter: Hunter) -> None:
        self._hunters[name] = hunter

    def names(self) -> List[str]:
        return list(self._hunters)

    def judge(self, name: str) -> Dict:
        """Exécute le chasseur, le juge via le CRITIC, logge le verdict et les gates appliquées.

        V1 — n_trials réel : le DSR doit déflater par le VRAI nombre d'essais du
        multiple-testing = au moins le nombre de hunters enregistrés (chaque hunter
        est un essai), et au plus le max avec la grille interne déclarée par la famille.
        Sinon le DSR sous-déflate → gate cosmétique.
        """
        if name not in self._hunters:
            raise KeyError(f"chasseur inconnu : {name}")
        return self._judge_inputs(name, self._hunters[name]())

    def _judge_inputs(self, name: str, inp: Dict,
                      sr_variance: Optional[float] = None) -> Dict:
        effective_n_trials = max(inp.get("n_trials", 1), len(self._hunters))
        sr_var = sr_variance if sr_variance is not None else inp.get("sr_variance", 0.05)
        v = evaluate_edge(
            inp_get(inp, "strat"), inp_get(inp, "bench"),
            n_trials=effective_n_trials,
            sr_variance=sr_var,
            pbo_matrix=inp.get("pbo_matrix"),
            permutation=inp.get("permutation"),
        )
        v["gates"]["effective_n_trials"] = effective_n_trials
        v["gates"]["sr_variance"] = round(sr_var, 6)
        res = {"name": name, "pass": v["pass"], "reasons": v["reasons"],
               "gates_applied": v["gates_applied"], "gates": v["gates"]}
        self._results[name] = res
        if self._memory is not None:
            self._memory.record({"hypothesis": {"signal": {"type": name}},
                                 "venue": "hunt", "pass": v["pass"],
                                 "reasons": v["reasons"],
                                 "gates_applied": v["gates_applied"], "gates": v["gates"]})
            self._memory.save()
        return res

    def hunt_all(self) -> List[Dict]:
        """Juge TOUS les chasseurs enregistrés (la chasse complète).

        Le DSR déflate par la variance des Sharpe DES ESSAIS (Bailey & López de Prado),
        dans l'unité des returns. On la MESURE sur les chasseurs de la chasse au lieu du
        0.05 codé en dur : sur des barres horaires ce 0.05 fixait la barre à un Sharpe de
        0.35 par barre, et la chasse du 16/09 rendait DSR=0.00 pour les 10 familles.
        """
        inputs = {n: h() for n, h in self._hunters.items()}
        sharpes = [_sharpe(inp_get(inp, "strat")) for inp in inputs.values()]
        var = statistics.pvariance(sharpes) if len(sharpes) >= 2 else None
        return [self._judge_inputs(n, inp, sr_variance=var) for n, inp in inputs.items()]

    def leaderboard(self) -> List[Dict]:
        """Classe les résultats : survivants d'abord, puis par Sharpe décroissant."""
        rows = list(self._results.values())
        return sorted(rows, key=lambda r: (r["pass"], r["gates"].get("sharpe", 0.0)),
                      reverse=True)


def inp_get(inp: Dict, key: str):
    if key not in inp:
        raise KeyError(f"le hunter doit fournir '{key}'")
    return inp[key]
