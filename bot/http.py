"""Session HTTP commune avec réessais et en-têtes de navigateur."""
from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def nouvelle_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "ja,en;q=0.8,fr;q=0.6",
    })
    return s


def requete(session: requests.Session, methode: str, url: str, essais: int = 3, **kwargs) -> requests.Response:
    """Requête avec réessais exponentiels (2 s, 4 s, 8 s) sur erreurs réseau / 429 / 5xx."""
    kwargs.setdefault("timeout", 25)
    derniere_erreur: Exception | None = None
    for i in range(essais):
        try:
            r = session.request(methode, url, **kwargs)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            derniere_erreur = e
            attente = 2 ** (i + 1)
            log.warning("Requête échouée (%s) %s — nouvel essai dans %ss", e, url[:80], attente)
            time.sleep(attente)
    assert derniere_erreur is not None
    raise derniere_erreur
