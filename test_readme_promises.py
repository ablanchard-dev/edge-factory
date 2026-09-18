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

import pytest

RACINE = Path(__file__).resolve().parent
FICHIERS_DE_RECHERCHE = ("_equities_research.json", "_xs_research.json", "hunt_memory.json")

# Les primitives par lesquelles du texte devient du code exécuté.
PRIMITIVES_DANGEREUSES = {"eval", "exec", "compile", "__import__"}
APPELS_DANGEREUX = {"loads"}  # pickle.loads / marshal.loads

# ⚠️ 18/09/2026 — CE QUE CETTE GARDE NE VOYAIT PAS.
#
# Elle reconnaissait quatre primitives et un `.loads`. Mesuré en lui présentant d'autres façons
# de faire exécuter du texte : **4 sur 15**. Passaient `os.system`, `subprocess.run`,
# `importlib.import_module`, `yaml.load`, `types.FunctionType` — et surtout, pour un dépôt quant,
# **`df.query(expression)` et `pd.eval(expression)`** : pandas ÉVALUE la chaîne. Router une
# expression de DSL vers `df.query()` est le raccourci naturel, et il défait exactement la
# promesse du README (« a safe DSL, no arbitrary code execution »).
#
# Mesure sur le dépôt : **aucune de ces voies n'existe**, sauf UNE — `call_llm_claude` lance
# `subprocess.run(["claude", "--print", prompt])`. Lue : liste d'arguments fixe, pas de
# `shell=True`, le prompt est un ARGUMENT, jamais une commande. C'est le canal de l'agent LLM
# que le README annonce, pas une exécution de DSL.
#
# 🔑 D'où ce lot : on reconnaît la CAPACITÉ (faire exécuter quelque chose), et l'unique voie
# légitime est NOMMÉE. Une absence devient une serrure : un second appel, moins soigné, tombe.
ATTRIBUTS_QUI_EXECUTENT = {
    "system": {"os"},                       # os.system("...")
    "popen": {"os"},                        # os.popen("...")
    "run": {"subprocess"},                  # subprocess.run([...])
    "call": {"subprocess"},
    "check_output": {"subprocess"},
    "check_call": {"subprocess"},
    "Popen": {"subprocess"},
    "import_module": {"importlib"},         # importe un module nommé par du texte
    "load": {"yaml"},                       # constructeurs arbitraires sans loader sûr
    "FunctionType": {"types"},              # fabrique une fonction depuis du bytecode
}

# `eval` et `query` en méthode : `df.eval(expr)` / `df.query(expr)` évaluent la chaîne.
# `model.evaluate(X, y)` porte un AUTRE nom et n'est donc pas concerné — la comparaison est
# exacte, jamais un préfixe.
METHODES_QUI_EVALUENT = {"eval", "query"}

# L'unique voie d'exécution du dépôt, nommée et justifiée. Par FICHIER et fonction : un appel
# identique ailleurs n'hérite pas de cette permission.
EXECUTIONS_AUTORISEES = {
    "llm_hypothesis.py:call_llm_claude":
        "le canal de l'agent LLM annoncé par le README : argv fixe, pas de shell, "
        "le prompt est un argument et jamais une commande",
}


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


def _ce_qui_execute(noeud: ast.Call) -> str | None:
    """Le nom de la capacité si cet appel peut faire exécuter quelque chose, sinon None."""
    f = noeud.func
    if isinstance(f, ast.Name) and f.id in PRIMITIVES_DANGEREUSES:
        return f"{f.id}()"
    if not isinstance(f, ast.Attribute):
        return None
    porteur = ast.unparse(f.value).split(".")[-1]
    # `json.loads` est inoffensif ; `pickle.loads` / `marshal.loads` ne le sont pas.
    if f.attr in APPELS_DANGEREUX and porteur in {"pickle", "marshal", "dill", "cPickle"}:
        return f"{porteur}.{f.attr}()"
    if f.attr in ATTRIBUTS_QUI_EXECUTENT and porteur in ATTRIBUTS_QUI_EXECUTENT[f.attr]:
        return f"{porteur}.{f.attr}()"
    # `df.eval(expr)` / `df.query(expr)` : pandas évalue la chaîne. `ast.literal_eval` est SÛR
    # par construction — c'est la bonne réponse à `eval`, on ne l'accuse pas.
    if f.attr in METHODES_QUI_EVALUENT and porteur != "ast":
        return f"…{f.attr}()"
    return None


def code_arbitraire(racine: Path) -> list[str]:
    """Les endroits du code livré où du texte pourrait devenir du code exécuté.

    La permission se lit par FICHIER et fonction englobante : un appel identique ailleurs
    n'hérite pas de l'autorisation accordée à celui-ci.
    """
    fautes: list[str] = []
    for chemin in _sources(racine):
        rel = chemin.relative_to(racine).as_posix()
        arbre = ast.parse(chemin.read_text(encoding="utf-8-sig"), filename=str(chemin))

        # Chaque appel, avec le nom de la fonction qui le porte ("<module>" au premier niveau).
        porteurs: list[tuple[ast.Call, str]] = []
        for n in ast.walk(arbre):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                porteurs += [(c, n.name) for c in ast.walk(n) if isinstance(c, ast.Call)]
        dans_une_fonction = {id(c) for c, _ in porteurs}
        porteurs += [(c, "<module>") for c in ast.walk(arbre)
                     if isinstance(c, ast.Call) and id(c) not in dans_une_fonction]

        for appel, fonction in porteurs:
            capacite = _ce_qui_execute(appel)
            if capacite is None:
                continue
            if f"{rel}:{fonction}" in EXECUTIONS_AUTORISEES:
                continue
            fautes.append(f"{rel}:{appel.lineno} {capacite}  (dans {fonction})")
    return sorted(set(fautes))


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


def _capacite(code: str) -> str | None:
    """La capacité d'exécution d'un appel isolé, pour les deux preuves ci-dessous."""
    appel = ast.parse(code).body[0].value
    return _ce_qui_execute(appel)


@pytest.mark.parametrize(
    "code,quoi",
    [
        ("eval(expr)", "deja vue"),
        ("exec(src)", "deja vue"),
        ("pickle.loads(b)", "deja vue"),
        ("marshal.loads(b)", "deja vue"),
        ("os.system(cmd)", "commande shell"),
        ("os.popen(cmd)", "commande shell"),
        ("subprocess.run(cmd)", "processus"),
        ("subprocess.Popen(cmd)", "processus"),
        ("subprocess.check_output(cmd)", "processus"),
        ("importlib.import_module(nom)", "module nomme par du texte"),
        ("yaml.load(t)", "constructeurs arbitraires sans loader sur"),
        ("types.FunctionType(code, {})", "fonction depuis du bytecode"),
        ("df.query(expression)", "pandas EVALUE la chaine"),
        ("pd.eval(expression)", "pandas EVALUE la chaine"),
        ("df.eval(expression)", "pandas EVALUE la chaine"),
    ],
)
def test_le_garde_voit_chaque_facon_de_faire_executer(code, quoi):
    """🔴 La version d'hier en voyait 4 sur 15, sans que rien ne le dise.

    Un garde qui reconnait quatre orthographes teste surtout que rien ne s'appelle comme elles.
    """
    assert _capacite(code) is not None, f"aveugle sur : {code}  ({quoi})"


@pytest.mark.parametrize(
    "code,pourquoi",
    [
        ("json.loads(t)", "lecture JSON"),
        ("ast.literal_eval(t)", "SUR par construction — c'est la bonne reponse a eval"),
        ("model.evaluate(X, y)", "'evaluate' n'est pas 'eval' : la comparaison est exacte"),
        ("df.filter(items=cols)", "selection de colonnes"),
        ("np.load(f)", "'load' n'est dangereux que porte par yaml"),
        ("session.run(x)", "'run' n'est dangereux que porte par subprocess"),
    ],
)
def test_le_garde_n_accuse_pas_ce_qui_n_execute_rien(code, pourquoi):
    """Le contrepoids : une garde qui refuse tout se fait retirer."""
    assert _capacite(code) is None, f"faux positif sur {code} ({pourquoi})"


def test_l_unique_voie_d_execution_est_nommee_et_justifiee():
    """L'absence devient une serrure : la seule exécution du dépôt porte son nom et sa raison.

    Sans cette liste, `subprocess.run` serait soit interdit — et le canal LLM annoncé par le
    README cesserait d'exister — soit toléré partout, et un second appel moins soigné passerait.
    """
    assert EXECUTIONS_AUTORISEES, "une liste vide rendrait la garde muette sur ce point"
    for cle, raison in EXECUTIONS_AUTORISEES.items():
        fichier, fonction = cle.split(":")
        assert (RACINE / fichier).exists(), f"{fichier} a disparu : la permission ne vise plus rien"
        assert raison.strip(), f"{cle} est autorisee sans raison ecrite"
        source = (RACINE / fichier).read_text(encoding="utf-8-sig")
        assert f"def {fonction}(" in source, f"{fonction} n'existe plus dans {fichier}"
        # La raison invoquee tient sur une propriete verifiable : pas de shell.
        assert "shell=True" not in source, f"{fichier} a gagne un shell : la raison ne tient plus"


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
