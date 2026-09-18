"""La preuve que le blocage réseau de `conftest.py` mord encore.

Il vit dans un fichier COLLECTÉ, et c'est délibéré : le même contrôle écrit dans `conftest.py`
ne tournerait jamais, et le compte de tests ne bougerait pas — c'est exactement comme ça qu'une
garde devient décorative sans que personne ne s'en aperçoive.
"""
import socket

import pytest


def test_le_blocage_reseau_MORD_vraiment():
    """🔴 Un bloqueur devenu inopérant laisse passer exactement ce qu'il doit arrêter.

    La suite resterait verte, et « no network » ne serait plus tenu par rien, sans qu'aucune
    ligne ne change.
    """
    # On ne fait PAS `from conftest import ...` : selon la disposition du depot, le dossier du
    # conftest n'est pas sur `sys.path`. Verifier le NOM ecarte aussi un faux positif : une
    # panne DNS leve `gaierror`, pas ca.
    with pytest.raises(Exception) as leve:
        socket.create_connection(("example.com", 80), timeout=1)
    assert type(leve.value).__name__ == "SortieReseauInterdite", (
        f"la sortie a echoue pour une autre raison ({type(leve.value).__name__})"
    )


def test_la_boucle_locale_reste_ouverte():
    """Le contrepoids : couverture et débogueur s'en servent. Tout interdire testerait pytest,
    et une garde insupportable finit par être retirée."""
    serveur = socket.socket()
    serveur.bind(("127.0.0.1", 0))
    serveur.listen(1)
    try:
        with socket.create_connection(serveur.getsockname(), timeout=2):
            pass
    finally:
        serveur.close()
