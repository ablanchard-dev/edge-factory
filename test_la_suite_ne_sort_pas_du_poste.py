"""La preuve que le blocage réseau de `conftest.py` mord encore.

Il vit dans un fichier COLLECTÉ, et c'est délibéré : le même contrôle écrit dans `conftest.py`
ne tournerait jamais, et le compte de tests ne bougerait pas — c'est exactement comme ça qu'une
garde devient décorative sans que personne ne s'en aperçoive.
"""
import socket

import pytest

from conftest import SortieReseauInterdite


def test_le_blocage_reseau_MORD_vraiment():
    """🔴 Un bloqueur devenu inopérant laisse passer exactement ce qu'il doit arrêter.

    La suite resterait verte, et « no network » ne serait plus tenu par rien, sans qu'aucune
    ligne ne change.
    """
    with pytest.raises(SortieReseauInterdite):
        socket.create_connection(("example.com", 80), timeout=1)


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
