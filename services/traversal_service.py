"""Moteur d'ordre de parcours — détermine le côté et l'ordre
d'apparition de chaque parcelle le long d'une rue.

Règle exacte de l'utilisateur : pas d'ordre gauche/droite imposé, mais
il faut finir un côté entier avant de passer à l'autre, en respectant
l'ordre d'apparition du parcours (pas un tri par numéro ou alphabétique).

Approche retenue (voir le plan) : reconstruire une polyligne à partir
des points d'adresse BAN partageant le même `voie_id`, groupés par
parité pair/impair (convention française : les deux côtés d'une rue
portent des numéros de parités opposées), ordonnés par numéro croissant
au sein de chaque côté — PAS un ajustement linéaire global (PCA), qui a
montré une vraie limite sur les rues courbes en investigation live."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from models.adresse import AdressePoint
from models.parcelle import Parcelle


def _numero_entier(housenumber: str) -> int:
    """Partie numérique d'un numéro de voirie (`"1bis"` -> `1`) pour le
    tri par numéro croissant au sein d'un côté."""
    m = re.match(r"\d+", housenumber.strip())
    return int(m.group()) if m else 0


def _vers_metres(lon: float, lat: float, lat_ref: float) -> Tuple[float, float]:
    """Projection plane approximative (mètres), valable seulement à
    l'échelle d'une rue/petite zone — mêmes constantes que la
    vérification PCA de l'investigation live (111320 m/degré de
    latitude, corrigé par cos(latitude) pour la longitude)."""
    x = lon * math.cos(math.radians(lat_ref)) * 111320
    y = lat * 111320
    return x, y


@dataclass
class PositionParcours:
    cote: str  # "pair" / "impair"
    chainage: float  # distance cumulée depuis le début du côté, en mètres
    distance_segment: float  # distance perpendiculaire au segment le plus proche (diagnostic)


class TraversalService:
    def construire_cotes(self, adresses: List[AdressePoint]) -> Dict[str, List[AdressePoint]]:
        """Groupe les adresses par parité, triées par numéro croissant —
        une polyligne par côté, jamais une seule droite globale."""
        pairs = sorted(
            (a for a in adresses if a.numero_parite == "pair"),
            key=lambda a: _numero_entier(a.housenumber),
        )
        impairs = sorted(
            (a for a in adresses if a.numero_parite == "impair"),
            key=lambda a: _numero_entier(a.housenumber),
        )
        return {"pair": pairs, "impair": impairs}

    @staticmethod
    def ordre_cotes(cotes: Dict[str, List[AdressePoint]]) -> List[str]:
        """Détermine quel côté démarre le parcours : celui contenant le
        plus petit numéro de voirie — confirmé en investigation live
        (Rue du Lardon) : les deux côtés d'une rue démarrent près du
        même bout (adresses 1 et 2 physiquement voisines), le numéro le
        plus bas indique donc le point de départ naturel du parcours.
        Pas un choix arbitraire gauche/droite (l'utilisateur n'en impose
        aucun), mais un point de départ géographique cohérent, déduit
        des données plutôt que deviné."""
        def plus_petit_numero(cote: str) -> float:
            points = cotes.get(cote) or []
            return min((_numero_entier(a.housenumber) for a in points), default=float("inf"))
        return sorted(cotes.keys(), key=plus_petit_numero)

    def positionner_sur_polyligne_reelle(
        self, centroide_lon: float, centroide_lat: float,
        polyligne: List[Tuple[float, float]], lat_ref: float,
    ) -> Optional[Tuple[float, float, float]]:
        """Projette un point sur une polyligne RÉELLE (plusieurs segments
        consécutifs, voir `services/voirie_service.py`) — renvoie
        `(chainage, distance_perpendiculaire, signe_cote)` où `signe_cote`
        est le signe du produit vectoriel (côté gauche/droit du sens de
        parcours de la polyligne telle que renvoyée par BDTOPO, pas
        encore calibré pair/impair — voir `main.py::decouvrir_parcelles`
        pour la calibration à partir des adresses connues, jamais
        deviné). `None` si la polyligne a moins de 2 points."""
        if len(polyligne) < 2:
            return None
        meilleur: Optional[Tuple[float, float, float]] = None
        chainage_debut = 0.0
        px, py = _vers_metres(centroide_lon, centroide_lat, lat_ref)
        for a, b in zip(polyligne, polyligne[1:]):
            ax, ay = _vers_metres(a[0], a[1], lat_ref)
            bx, by = _vers_metres(b[0], b[1], lat_ref)
            t, dist_perp, longueur = _projeter_sur_segment(px, py, ax, ay, bx, by)
            chainage = chainage_debut + t * longueur
            if meilleur is None or dist_perp < meilleur[1]:
                cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
                meilleur = (chainage, dist_perp, cross)
            chainage_debut += longueur
        return meilleur

    def positionner_parcelle(
        self, centroide_lon: float, centroide_lat: float, cotes: Dict[str, List[AdressePoint]],
    ) -> Optional[PositionParcours]:
        """Projette une parcelle sur le segment le plus proche, tous
        côtés confondus — le côté du segment le plus proche détermine le
        côté de la parcelle, la position projetée + la distance cumulée
        jusqu'au début de ce segment donnent le chaînage."""
        meilleure: Optional[PositionParcours] = None
        for cote, points in cotes.items():
            if len(points) < 2:
                # Un seul point (ou aucun) sur ce côté : pas de segment à
                # projeter dessus, on ignore (une parcelle isolée sans
                # voisin adressé sur ce côté retombera sur l'autre côté,
                # ou restera non positionnée si aucun côté n'a assez de
                # points — comportement acceptable pour une rue quasi
                # vide, à revoir seulement si ça se présente en pratique).
                continue
            lat_ref = points[0].lat
            px, py = _vers_metres(centroide_lon, centroide_lat, lat_ref)
            chainage_debut = 0.0
            for a, b in zip(points, points[1:]):
                ax, ay = _vers_metres(a.lon, a.lat, lat_ref)
                bx, by = _vers_metres(b.lon, b.lat, lat_ref)
                t, dist_perp, longueur_segment = _projeter_sur_segment(px, py, ax, ay, bx, by)
                chainage = chainage_debut + t * longueur_segment
                if meilleure is None or dist_perp < meilleure.distance_segment:
                    meilleure = PositionParcours(cote=cote, chainage=chainage, distance_segment=dist_perp)
                chainage_debut += longueur_segment
        return meilleure

    @staticmethod
    def trier(
        parcelles_positionnees: List[Tuple[Parcelle, PositionParcours]],
        cotes_ordonnes: List[str],
    ) -> List[Parcelle]:
        """Trie : un côté entier (le premier de `cotes_ordonnes`, voir
        `ordre_cotes`) puis l'autre — règle exacte de l'utilisateur.

        Confirmé en investigation live sur une vraie rue à 27 parcelles
        (Rue du Lardon) : la marche réelle est de "monter" le premier
        côté en chaînage CROISSANT jusqu'au bout de la rue, puis
        traverser et "redescendre" le second côté en chaînage
        DÉCROISSANT pour revenir vers le point de départ — trier les
        deux côtés en croissant (une première version le faisait)
        produit un ordre incohérent avec un vrai parcours à pied,
        confirmé faux puis corrigé sur ces mêmes données réelles."""
        par_cote: Dict[str, List[Tuple[Parcelle, PositionParcours]]] = {}
        for parcelle, position in parcelles_positionnees:
            par_cote.setdefault(position.cote, []).append((parcelle, position))

        resultat: List[Parcelle] = []
        premier = True
        for cote in cotes_ordonnes:
            if cote not in par_cote:
                continue
            groupe = sorted(par_cote[cote], key=lambda pc: pc[1].chainage, reverse=not premier)
            for parcelle, position in groupe:
                parcelle.cote = position.cote
                parcelle.ordre = position.chainage
                resultat.append(parcelle)
            premier = False
        return resultat


def _projeter_sur_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float,
) -> Tuple[float, float, float]:
    """Projection du point (px,py) sur le segment [A,B] — renvoie
    `(t, distance_perpendiculaire, longueur_du_segment)` avec `t` dans
    `[0, 1]` (bloqué aux extrémités, pas de projection hors segment)."""
    dx, dy = bx - ax, by - ay
    longueur = math.hypot(dx, dy)
    if longueur == 0:
        return 0.0, math.hypot(px - ax, py - ay), 0.0
    t = ((px - ax) * dx + (py - ay) * dy) / (longueur ** 2)
    t = max(0.0, min(1.0, t))
    proj_x, proj_y = ax + t * dx, ay + t * dy
    dist_perp = math.hypot(px - proj_x, py - proj_y)
    return t, dist_perp, longueur
