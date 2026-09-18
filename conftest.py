"""« the test suite, no network » — la promesse du README, tenue par la suite elle-même.

Mesuré le 18/09/2026 : les 304 tests passent avec TOUTE sortie réseau bloquée et les variables
de clé retirées de l'environnement. La promesse était vraie, et tenue par rien. Un test qui
appellerait une API passerait au vert sur une machine connectée et casserait chez qui clone,
sans qu'une ligne le dise.

Ce blocage vit ici plutôt que dans un test, parce qu'il doit s'installer AVANT tout import de
module de test. Sa preuve, elle, vit dans `test_la_suite_ne_sort_pas_du_poste.py` : un fichier
que pytest COLLECTE — un contrôle posé dans ce fichier-ci ne tournerait jamais.

La boucle locale reste ouverte : la couverture et le débogueur s'en servent, et l'interdire
testerait pytest plutôt que le produit.

Ce que ça ne concerne PAS : `run_hunt.py` interroge la vraie API Hyperliquid et
`llm_hypothesis.py` lance la CLI `claude`. Ce sont des points d'entrée, pas des tests — le
README les distingue déjà, et cette garde ne les touche pas.
"""
import socket as _socket

_CONNECT = _socket.socket.connect
_CONNECT_EX = _socket.socket.connect_ex


class SortieReseauInterdite(RuntimeError):
    """Un test a tenté de sortir. Le README promet que la suite n'en a pas besoin."""


def _est_local(adresse) -> bool:
    try:
        hote = adresse[0]
    except (TypeError, IndexError):
        return False
    return hote in {"127.0.0.1", "::1", "localhost", ""}


def _refuser(vrai):
    def _appel(self, adresse, *a, **kw):
        if not _est_local(adresse):
            raise SortieReseauInterdite(
                f"sortie réseau vers {adresse!r} — le README promet « no network »")
        return vrai(self, adresse, *a, **kw)
    return _appel


_socket.socket.connect = _refuser(_CONNECT)
_socket.socket.connect_ex = _refuser(_CONNECT_EX)
