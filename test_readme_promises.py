"""Les deux promesses du haut du README tiennent-elles par le code, ou par la chance ?

Le README ouvre sur deux affirmations vérifiables, et aucune n'était tenue par un test :

  1. « **66 verdicts** are recorded in the committed research files » — un chiffre écrit à
     la main. Il est JUSTE aujourd'hui (12 + 12 + 42, compté le 18/09/2026), mais rien ne
     le suit : le 67e verdict le rend faux en silence. Un chiffre écrit à la main est une
     dette, comme les « 2 957 tests » de DrDXT qui en annonçaient 1 248 de moins que la
     réalité, ou les « 23 tests » de scamshield qui en cachaient 48.

  2. « proposes strategies through a **safe DSL** (no arbitrary code execution) » — c'est
     une promesse de SÉCURITÉ, et la plus lourde du dépôt : un agent LLM propose des
     stratégies, et le DSL est ce qui l'empêche d'exécuter ce qu'il veut sur la machine.
     Elle tient aujourd'hui — mesuré : aucun `eval`, `exec`, `compile`, `__import__` ni
     `pickle.loads` dans le code livré — mais par ABSENCE, pas par une serrure. Le jour où
     quelqu'un « simplifie » l'évaluateur du DSL avec un `eval`, rien ne rougit.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parent
FICHIERS_DE_RECHERCHE = ("_equities_research.json", "_xs_research.json", "hunt_memory.json")

# Les primitives par lesquelles du texte devient du code exécuté.
PRIMITIVES_DANGEREUSES = {"eval", "exec", "compile", "__import__"}
APPELS_DANGEREUX = {"loads"}  # pickle.loads / marshal.loads


def _sources(racine: Path) -> list[Path]:
    return [
        p for p in racine.rglob("*.py")
        if ".venv" not in p.parts
        and "site-packages" not in p.parts
        and not p.name.startswith("test_")
    ]


def verdicts_enregistres() -> int:
    total = 0
    for nom in FICHIERS_DE_RECHERCHE:
        donnees = json.loads((RACINE / nom).read_text(encoding="utf-8"))
        assert isinstance(donnees, list), f"{nom} n'est plus une liste de verdicts"
        total += len(donnees)
    return total


def verdicts_annonces() -> int:
    texte = (RACINE / "README.md").read_text(encoding="utf-8")
    trouve = re.search(r"\*\*(\d+) verdicts\*\*|\((\d+) verdicts are recorded", texte)
    assert trouve, "le README n'annonce plus de nombre de verdicts"
    return int(trouve.group(1) or trouve.group(2))


def code_arbitraire(racine: Path) -> list[str]:
    """Les endroits du code livré où du texte pourrait devenir du code exécuté."""
    fautes: list[str] = []
    for chemin in _sources(racine):
        arbre = ast.parse(chemin.read_text(encoding="utf-8-sig"), filename=str(chemin))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            f = noeud.func
            if isinstance(f, ast.Name) and f.id in PRIMITIVES_DANGEREUSES:
                fautes.append(f"{chemin.relative_to(racine).as_posix()}:{noeud.lineno} {f.id}()")
            elif isinstance(f, ast.Attribute) and f.attr in APPELS_DANGEREUX:
                # `json.loads` est inoffensif ; `pickle.loads` / `marshal.loads` ne le sont pas.
                porteur = ast.unparse(f.value)
                if porteur.split(".")[-1] in {"pickle", "marshal", "dill", "cPickle"}:
                    fautes.append(
                        f"{chemin.relative_to(racine).as_posix()}:{noeud.lineno} {porteur}.{f.attr}()")
    return fautes


def test_le_nombre_de_verdicts_du_README_est_celui_des_fichiers():
    reels = verdicts_enregistres()
    assert reels > 0, "plus aucun verdict enregistre : le garde ne garde plus rien"
    assert verdicts_annonces() == reels, (
        f"le README annonce {verdicts_annonces()} verdicts, les fichiers en contiennent {reels}"
    )


def verdicts_qui_passent(fichiers=FICHIERS_DE_RECHERCHE, racine=RACINE) -> list[str]:
    """Les hypothèses enregistrées que le critique a laissées passer.

    Chaque entrée DOIT porter la clé `pass` : une entrée qui ne la porte pas serait
    comptée comme un échec par défaut, et c'est exactement ainsi qu'un succès
    disparaîtrait sans bruit.
    """
    qui_passent: list[str] = []
    for nom in fichiers:
        donnees = json.loads((racine / nom).read_text(encoding="utf-8"))
        for i, entree in enumerate(donnees):
            assert "pass" in entree, f"{nom}[{i}] n'a pas de verdict `pass` : illisible, pas negatif"
            if entree["pass"]:
                qui_passent.append(f"{nom}[{i}] {entree.get('hypothesis', '?')}")
    return qui_passent


def test_le_titre_honnete_du_README_est_vrai_dans_les_fichiers():
    """« this machine found **no robust, tradable edge** » — la phrase en gras du README.

    C'est l'affirmation sur laquelle repose tout le depot : un outil qui dit « non » vaut
    mieux qu'un outil qui flatte. Elle etait ecrite, comptee (66 verdicts), et **verifiee
    par personne** — le garde du dessus compte les verdicts sans jamais regarder ce qu'ils
    disent. Mesure du 18/09/2026 : 12 + 12 + 42 = 66 entrees, toutes a `pass: False`.

    Ce test est a double sens, et c'est voulu. Le jour ou une hypothese passera, il tombera
    et forcera a reecrire le titre. Une bonne nouvelle qui laisse le README mentir reste un
    README qui ment.
    """
    qui_passent = verdicts_qui_passent()
    assert not qui_passent, (
        "le README dit que la machine n'a trouve AUCUN edge robuste ; ces verdicts disent "
        "le contraire — mettre le titre a jour :\n  " + "\n  ".join(qui_passent)
    )


def test_le_garde_VOIT_un_verdict_qui_passe(tmp_path):
    """Sans ceci, le test du dessus prouverait surtout que `pass` ne vaut jamais vrai."""
    (tmp_path / "faux_research.json").write_text(
        json.dumps([
            {"hypothesis": "momentum 12-1", "pass": False},
            {"hypothesis": "un edge qui aurait survecu", "pass": True},
        ]),
        encoding="utf-8",
    )
    trouve = verdicts_qui_passent(("faux_research.json",), tmp_path)
    assert len(trouve) == 1 and "aurait survecu" in trouve[0], trouve


def test_un_verdict_sans_cle_pass_est_refuse_pas_compte_comme_un_echec(tmp_path):
    """Le contrepoids : un fichier dont la forme change ne doit pas rendre le garde muet."""
    (tmp_path / "faux_research.json").write_text(
        json.dumps([{"hypothesis": "forme inconnue", "verdict": "rejected"}]),
        encoding="utf-8",
    )
    try:
        verdicts_qui_passent(("faux_research.json",), tmp_path)
    except AssertionError as e:
        assert "illisible" in str(e)
    else:
        raise AssertionError("une entree sans `pass` doit etre nommee, pas avalee")


def compte_des_fichiers(racine=RACINE) -> tuple[int, int]:
    """(modules, fichiers de test) du dépôt, selon la même définition que `_sources`."""
    tous = [
        p for p in racine.rglob("*.py")
        if not any(part in {".venv", "site-packages", "__pycache__", ".pytest_cache"}
                   for part in p.parts)
    ]
    tests = [p for p in tous if p.name.startswith("test_")]
    return len(tous) - len(tests), len(tests)


def test_l_arborescence_du_README_compte_les_fichiers_qui_existent():
    """« 75 modules + 43 test files (17/09/2026) ».

    Mesure du 18/09/2026 : 75 modules — juste — et **44** fichiers de test. Un chiffre
    ecrit a la main la veille etait deja faux le lendemain, et sa date ne le rattrape pas :
    elle dit seulement quand il a cesse d'etre verifie. Il se deduit maintenant.
    """
    modules, tests = compte_des_fichiers()
    texte = (RACINE / "README.md").read_text(encoding="utf-8")
    trouve = re.search(r"(\d+) modules \+ (\d+) test files", texte)
    assert trouve, "l'arborescence du README n'annonce plus de compte de fichiers"
    assert (int(trouve.group(1)), int(trouve.group(2))) == (modules, tests), (
        f"le README annonce {trouve.group(1)} modules + {trouve.group(2)} fichiers de test, "
        f"le depot en contient {modules} + {tests}"
    )


def test_le_code_livre_n_execute_aucun_texte():
    fautes = code_arbitraire(RACINE)
    assert not fautes, (
        "le README promet « no arbitrary code execution » ; ces appels le contredisent :\n  "
        + "\n  ".join(fautes)
    )


def test_le_garde_VOIT_un_eval_ajoute(tmp_path):
    """Un garde qu'on ne peut pas faire tomber sur commande ne prouve rien.

    Sans lui, le test du dessus prouverait surtout que la recherche ne trouve rien.
    """
    (tmp_path / "dsl_simplifie.py").write_text(
        "def evaluer(expression, ctx):\n"
        "    return eval(expression, {}, ctx)\n",
        encoding="utf-8",
    )
    (tmp_path / "cache.py").write_text(
        "import pickle\n"
        "def charger(b):\n"
        "    return pickle.loads(b)\n",
        encoding="utf-8",
    )

    fautes = code_arbitraire(tmp_path)

    assert any("eval()" in f for f in fautes), fautes
    assert any("pickle.loads()" in f for f in fautes), fautes


def test_json_loads_n_est_pas_accuse(tmp_path):
    """Le contrepoids : sans lui, on aurait pu interdire tout `.loads` et croire le garde
    satisfait — alors que le dépôt lit ses verdicts avec `json.loads`."""
    (tmp_path / "lecture.py").write_text(
        "import json\n"
        "def lire(t):\n"
        "    return json.loads(t)\n",
        encoding="utf-8",
    )

    assert code_arbitraire(tmp_path) == []
