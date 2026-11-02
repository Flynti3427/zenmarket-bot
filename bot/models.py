"""Structures de données partagées par tout le bot."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

Fourchette = tuple[float, float]  # (bas, haut) en euros

ETATS = ("tres_bon", "moyen", "mauvais")


@dataclass
class Listing:
    """Une annonce trouvée sur Mercari ou Yahoo Enchères."""

    source: str                 # "mercari" | "mercari_shops" | "yahoo"
    item_id: str
    title: str
    price_jpy: int
    url_original: str
    url_zenmarket: str
    image_url: Optional[str] = None
    condition_jp: Optional[str] = None   # libellé d'état japonais si connu
    is_auction: bool = False
    buy_now_jpy: Optional[int] = None    # prix "achat immédiat" d'une enchère
    time_left: Optional[str] = None      # temps restant d'une enchère (texte)
    fin_ts: Optional[float] = None       # heure de fin de l'enchère (timestamp Unix)
    seller_id: Optional[str] = None      # identifiant du vendeur (Mercari)
    photos: list = field(default_factory=list)       # jusqu'à 3 photos (détail Mercari)
    vendeur_avis: Optional[int] = None               # nombre d'évaluations du vendeur
    vendeur_positif_pct: Optional[int] = None        # % d'évaluations positives

    @property
    def key(self) -> str:
        return f"{self.source}:{self.item_id}"


def lire_fourchette(valeur) -> Optional[Fourchette]:
    """400 -> (400, 400) ; [400, 450] -> (400, 450) ; null -> None."""
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, (int, float)):
        return (float(valeur), float(valeur))
    bas, haut = valeur
    return (float(bas), float(haut))


def _groupes(valeur) -> list[list[str]]:
    """[a, b] -> [[a, b]] ; [[a, b], [c]] -> tel quel ; mots en minuscules."""
    if not valeur:
        return []
    if all(not isinstance(v, list) for v in valeur):
        valeur = [valeur]
    return [[str(m).lower() for m in g] for g in valeur if g]


def lire_par_etat(d: dict | None) -> dict[str, Optional[Fourchette]]:
    d = d or {}
    return {e: lire_fourchette(d.get(e)) for e in ETATS}


@dataclass
class Article:
    """Un article recherché (ligne du config.yaml)."""

    nom: str
    recherches: list[str]
    doit_contenir: list[str]
    exclure: list[str]
    prix_min_jpy: int
    profil: str
    achat: dict = field(default_factory=dict)    # prix d'achat visé (coût rendu France) par état
    revente: dict = field(default_factory=dict)  # prix de revente par état
    achat_tous_etats: Optional[float] = None     # seuil unique quel que soit l'état (ex. Speedy 450 €)
    salon: Optional[str] = None                  # salon Discord forcé (ex. « wallet »), sinon celui de la marque
    fil: Optional[str] = None                    # fil Discord dans ce salon (ex. « keepall » dans louis-vuitton)
    sans_limite: bool = False                    # alerte pour toute nouvelle annonce, quel que soit le prix
    doit_contenir_aussi: list = field(default_factory=list)  # autres groupes : un mot de CHAQUE groupe requis

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        return cls(
            nom=d["nom"],
            recherches=list(d["recherches"]),
            doit_contenir=[str(s).lower() for s in d.get("doit_contenir", [])],
            exclure=[str(s).lower() for s in d.get("exclure", [])],
            prix_min_jpy=int(d.get("prix_min_jpy", 0)),
            profil=d.get("profil", "sac"),
            achat=lire_par_etat(d.get("achat")),
            revente=lire_par_etat(d.get("revente")),
            achat_tous_etats=float(d["achat_tous_etats"]) if d.get("achat_tous_etats") else None,
            salon=d.get("salon"),
            fil=d.get("fil"),
            sans_limite=bool(d.get("sans_limite", False)),
            doit_contenir_aussi=_groupes(d.get("doit_contenir_aussi")),
        )

    def seuil_achat(self, etat: str) -> Optional[Fourchette]:
        """Fourchette d'achat pour cet état.

        Si le tableau ne donne pas de prix pour « très bon », on reprend celui de « moyen » :
        payer le prix d'un 5/10 pour un 8/10 reste une bonne affaire.
        Jamais d'alerte pour « mauvais » sans prix explicite.

        Avec `achat_tous_etats`, le seuil d'alerte (haut) est ce prix pour tous les états,
        mauvais compris ; le bas reste celui du tableau (pour le marqueur « SOUS ta fourchette »).
        """
        f = self.achat.get(etat)
        if f is None and etat == "tres_bon":
            f = self.achat.get("moyen")
        if self.achat_tous_etats:
            ref = f or self.achat.get("moyen") or self.achat.get("tres_bon")
            bas = ref[0] if ref else self.achat_tous_etats
            haut = max(ref[1], self.achat_tous_etats) if f else self.achat_tous_etats
            return (min(bas, haut), haut)
        return f

    @property
    def a_des_prix(self) -> bool:
        return any(self.achat.values()) or bool(self.achat_tous_etats)

    def revente_pour(self, etat: str) -> Optional[Fourchette]:
        f = self.revente.get(etat)
        if f is None and etat == "tres_bon":
            f = self.revente.get("moyen")
        return f


def appliquer_seuil_unique(articles: list[Article]) -> None:
    """Réglage global : chaque article alerte sous son prix d'achat le plus haut, quel que soit l'état."""
    for a in articles:
        if a.achat_tous_etats:
            continue
        hauts = [f[1] for f in a.achat.values() if f]
        if hauts:
            a.achat_tous_etats = max(hauts)
