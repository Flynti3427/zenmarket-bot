"""Taux de change JPY -> EUR (taux de référence BCE via frankfurter.app), mis en cache 6 h."""
from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)
URL = "https://api.frankfurter.app/latest?from=JPY&to=EUR"


class TauxChange:
    def __init__(self, secours: float, session: requests.Session | None = None, ttl_s: int = 6 * 3600):
        self.secours = secours
        self.session = session or requests.Session()
        self.ttl_s = ttl_s
        self._taux: float | None = None
        self._date = 0.0

    def jpy_eur(self) -> float:
        if self._taux and time.time() - self._date < self.ttl_s:
            return self._taux
        try:
            r = self.session.get(URL, timeout=15)
            r.raise_for_status()
            self._taux = float(r.json()["rates"]["EUR"])
            self._date = time.time()
            log.info("Taux JPY->EUR du jour : %.6f", self._taux)
        except Exception as e:  # noqa: BLE001 — le bot ne doit jamais s'arrêter pour ça
            log.warning("Taux de change indisponible (%s), taux de secours %.6f", e, self.secours)
            return self._taux or self.secours
        return self._taux
