"""Mémoire du bot (SQLite) : annonces vues, alertes envoyées, favoris, vendeurs bloqués.

Utilisable depuis plusieurs threads (la recherche tourne à côté du bot Discord).
"""
from __future__ import annotations

import json
import sqlite3
import statistics
import threading
import time
from pathlib import Path


class Stockage:
    def __init__(self, chemin: str | Path):
        Path(chemin).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(chemin), check_same_thread=False)
        self.verrou = threading.Lock()
        with self.verrou:
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS vus (
                    cle TEXT PRIMARY KEY, article TEXT, titre TEXT, prix_jpy INTEGER,
                    cout_eur REAL, profit_eur REAL, url TEXT,
                    premier_vu REAL, dernier_vu REAL, prix_alerte_jpy INTEGER);
                CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
                CREATE TABLE IF NOT EXISTS alertes (cle TEXT PRIMARY KEY, donnees TEXT, envoyee REAL);
                CREATE TABLE IF NOT EXISTS favoris (cle TEXT PRIMARY KEY, ajoute REAL);
                CREATE TABLE IF NOT EXISTS bloques (valeur TEXT PRIMARY KEY, raison TEXT, ajoute REAL);
            """)
            self.db.commit()

    def _x(self, sql: str, params=(), commit=False):
        with self.verrou:
            cur = self.db.execute(sql, params)
            rows = cur.fetchall()
            if commit:
                self.db.commit()
            return rows

    # ------------------------------------------------------------ annonces vues
    def get(self, cle: str):
        rows = self._x("SELECT prix_jpy, prix_alerte_jpy FROM vus WHERE cle = ?", (cle,))
        return rows[0] if rows else None

    def enregistrer(self, cle, article, titre, prix_jpy, cout_eur, profit_eur, url, alerte: bool):
        maintenant = time.time()
        ancien = self.get(cle)
        prix_alerte = prix_jpy if alerte else (ancien[1] if ancien else None)
        self._x("""
            INSERT INTO vus (cle, article, titre, prix_jpy, cout_eur, profit_eur, url,
                             premier_vu, dernier_vu, prix_alerte_jpy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cle) DO UPDATE SET
                prix_jpy = excluded.prix_jpy, cout_eur = excluded.cout_eur,
                profit_eur = excluded.profit_eur, dernier_vu = excluded.dernier_vu,
                prix_alerte_jpy = excluded.prix_alerte_jpy
        """, (cle, article, titre, prix_jpy, cout_eur, profit_eur, url,
              maintenant, maintenant, prix_alerte), commit=True)

    def moins_chers(self, article: str, depuis_s: float = 86400, limite: int = 5):
        return self._x("""
            SELECT titre, prix_jpy, cout_eur, url FROM vus
            WHERE article = ? AND dernier_vu > ? ORDER BY cout_eur ASC LIMIT ?
        """, (article, time.time() - depuis_s, limite))

    def prix_habituel_jpy(self, article: str, depuis_jours: int = 30, minimum: int = 8) -> int | None:
        """Prix médian des annonces vues pour cet article (None s'il y a trop peu de données)."""
        rows = self._x("SELECT prix_jpy FROM vus WHERE article = ? AND dernier_vu > ?",
                       (article, time.time() - depuis_jours * 86400))
        prix = [r[0] for r in rows if r[0]]
        return int(statistics.median(prix)) if len(prix) >= minimum else None

    # ----------------------------------------------------------------- alertes
    def sauver_alerte(self, cle: str, donnees: dict):
        self._x("INSERT OR REPLACE INTO alertes (cle, donnees, envoyee) VALUES (?, ?, ?)",
                (cle, json.dumps(donnees, ensure_ascii=False), time.time()), commit=True)

    def encheres_qui_finissent(self, avant_ts: float) -> list[dict]:
        """Alertes d'enchères pas encore terminées dont la fin est avant `avant_ts`."""
        maintenant = time.time()
        res = []
        for (donnees,) in self._x("SELECT donnees FROM alertes"):
            a = json.loads(donnees)
            fin = a.get("fin_ts")
            if a.get("enchere") and fin and maintenant < fin <= avant_ts:
                res.append(a)
        return res

    def dernier_prix(self, cle: str):
        """(prix en ¥, moment où l'annonce a été vue pour la dernière fois) ou None."""
        rows = self._x("SELECT prix_jpy, dernier_vu FROM vus WHERE cle = ?", (cle,))
        return rows[0] if rows else None

    def alerte(self, cle: str) -> dict | None:
        rows = self._x("SELECT donnees FROM alertes WHERE cle = ?", (cle,))
        return json.loads(rows[0][0]) if rows else None

    # ----------------------------------------------------------------- favoris
    def basculer_favori(self, cle: str) -> bool:
        """Ajoute ou retire des favoris. Renvoie True si l'annonce est maintenant en favori."""
        if self._x("SELECT 1 FROM favoris WHERE cle = ?", (cle,)):
            self._x("DELETE FROM favoris WHERE cle = ?", (cle,), commit=True)
            return False
        self._x("INSERT INTO favoris (cle, ajoute) VALUES (?, ?)", (cle, time.time()), commit=True)
        return True

    def favoris(self, limite: int = 20) -> list[dict]:
        rows = self._x("""
            SELECT a.donnees FROM favoris f JOIN alertes a ON a.cle = f.cle
            ORDER BY f.ajoute DESC LIMIT ?""", (limite,))
        return [json.loads(r[0]) for r in rows]

    # ------------------------------------------------------- vendeurs bloqués
    def bloquer(self, valeur: str, raison: str = "arnaque"):
        self._x("INSERT OR REPLACE INTO bloques (valeur, raison, ajoute) VALUES (?, ?, ?)",
                (valeur, raison, time.time()), commit=True)

    def est_bloque(self, *valeurs: str | None) -> bool:
        vals = [v for v in valeurs if v]
        if not vals:
            return False
        marques = ",".join("?" * len(vals))
        return bool(self._x(f"SELECT 1 FROM bloques WHERE valeur IN ({marques})", vals))

    # -------------------------------------------------------------------- meta
    def meta_get(self, k: str):
        rows = self._x("SELECT v FROM meta WHERE k = ?", (k,))
        return rows[0][0] if rows else None

    def meta_set(self, k: str, v: str):
        self._x("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)", (k, v), commit=True)
