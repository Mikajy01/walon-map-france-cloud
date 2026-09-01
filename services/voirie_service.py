"""Géométrie réelle de voirie (BDTOPO, IGN) — utilisée pour construire une
polyligne PRÉCISE d'une rue plutôt que la reconstruction grossière à partir
des seules adresses BAN (voir traversal_service.py).

Écart réel trouvé en investigation live sur "Montée de la Quoille"
(Arboys en Bugey) : avec seulement 4 adresses réelles sur 14 parcelles, la
ligne droite reliant les 2 adresses de chaque côté ne suit pas du tout le
vrai virage d'une route de montagne — ordre de parcours incohérent, et
inclusion erronée de parcelles qui ne bordent pas réellement la rue (leur
distance à la ligne grossière sous-estime leur vraie distance à la route).

Source confirmée en direct : `data.geopf.fr/wfs/ows`, couche
`BDTOPO_V3:voie_nommee`, filtrée par `insee_commune`+`nom_voie_ban` — un
`MultiLineString` de plusieurs tronçons PAS garantis dans l'ordre de
parcours (confirmé : le tronçon 1 se termine où le tronçon 3 commence, pas
le tronçon 2), d'où le chaînage explicite par proximité d'extrémité."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.http_client import HttpClient
from utils.logger import get_logger
from utils.text_normalize import normaliser

_logger = get_logger("services.voirie_service")

_WFS_BASE = "https://data.geopf.fr/wfs/ows"
_EPSILON_DEGRES = 1e-7  # tolérance pour considérer 2 points comme identiques (proximité exacte)
# Tolérance beaucoup plus large (environ 10 m à 45° de latitude) pour le
# recollement "glouton" de tronçons séparés par un carrefour ou imprécision
# de digitalisation — écart réel : Route d'Etrez (Bresse Vallons) était
# tronquée au croisement (commençait au n°1560 au lieu du vrai début)
# parce que les 2 parties (avant/après carrefour) n'étaient pas à <1e-7°
# l'une de l'autre, donc la première (début de la rue) était purement
# ignorée, et la chaîne démarrait sur le tronçon du milieu.
_RACCORD_TOLERANCE_DEGRES = 1e-4


def _distance_deg(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Distance euclidienne brute en degrés — suffisante pour comparer
    QUEL extrémité est LA PLUS PROCHE d'une autre (ordre, pas valeur
    absolue). Évite le coût d'une projection pour une simple comparaison
    de voisinage sur l'échelle d'une rue (< 1 km)."""
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _chainer_parties(parties: List[List[Tuple[float, float]]]) -> List[Tuple[float, float]]:
    """Chaîne des tronçons de LineString (possiblement disjoints au
    niveau des carrefours) en UNE polyligne continue, avec un choix
    EXPLICITE de point de départ : on préfère commencer sur un tronçon
    dont une extrémité n'a AUCUN voisin proche parmi les autres
    tronçons — c'est donc un vrai BOUT DE LA RUE, et pas un point de
    raccord intermédiaire/carrefour. Sans ça, le premier tronçon de la
    liste (ordre arbitraire renvoyé par le WFS) peut être celui du
    milieu, au croisement — la chaîne démarrait alors au numéro 1560
    sur Route d'Etrez, au lieu du vrai début de la rue.

    Les tronçons restants sont ensuite accolés BOUT À BOUT par
    proximité GLoutone (le plus proche voisin, jamais rejeté faute de
    tolérance trop stricte) : même quand une rue est coupée en plusieurs
    morceaux indépendants par des carrefours (donc légèrement écartés
    numériquement), on les enchaîne quand même — on obtient un ordre
    de parcours global cohérent, indispensable pour que les numéros
    les plus bas correspondent bien au début du chainage.

    Porté/adapté de `project/utils/geometrie.py::_rechainer_chemins`
    (même logique déjà validée sur la version Wallonne), avec une
    tolérance additionnelle de raccord pour les points presque
    superposés."""
    if not parties:
        return []
    if len(parties) == 1:
        return list(parties[0])

    def _plus_proche_voisin(idx: int, extr: Tuple[float, float]) -> Optional[float]:
        meilleure: Optional[float] = None
        for j, autre in enumerate(parties):
            if j == idx:
                continue
            for extremite in (autre[0], autre[-1]):
                d = _distance_deg(extr, extremite)
                if meilleure is None or d < meilleure:
                    meilleure = d
        return meilleure

    depart_idx = 0
    inverser_depart = False
    seuil_isolement = _RACCORD_TOLERANCE_DEGRES ** 2
    for i in range(len(parties)):
        d_deb = _plus_proche_voisin(i, parties[i][0])
        d_fin = _plus_proche_voisin(i, parties[i][-1])
        debut_isole = d_deb is None or d_deb > seuil_isolement
        fin_isolee = d_fin is None or d_fin > seuil_isolement
        if debut_isole and not fin_isolee:
            depart_idx, inverser_depart = i, False
            break
        if fin_isolee and not debut_isole:
            depart_idx, inverser_depart = i, True
            break
    else:
        # Cas 1 : les DEUX extrémités d'un tronçon sont isolées (rue en
        # impasse totale, aucun voisin sur les deux côtés) — prend ce
        # tronçon au hasard (l'un de ses bouts servira de début).
        # Cas 2 : AUCUNE extrémité n'est clairement isolée (tous les
        # tronçons ont des voisins proches des deux côtés — typiquement
        # une rue qui démarre/termine SUR un carrefour, comme Route
        # d'Etrez à Bresse Vallons : l'ancien code prenait le premier
        # tronçon de la liste WFS, qui était celui du milieu au n°1560,
        # pas le vrai début). Solution : parmi TOUTES les extrémités de
        # TOUS les tronçons, prendre celle dont le plus proche voisin
        # est LE PLUS LOIN — c'est le "bout le plus bout" de la rue,
        # même si techniquement il a un voisin (le carrefour) à proximité.
        # Jamais l'arbitraire de l'ordre WFS.
        candidats: List[Tuple[float, int, bool]] = []  # (distance, idx_troncon, est_debut)
        for i in range(len(parties)):
            d_deb = _plus_proche_voisin(i, parties[i][0])
            d_fin = _plus_proche_voisin(i, parties[i][-1])
            if d_deb is not None:
                candidats.append((d_deb, i, True))
            if d_fin is not None:
                candidats.append((d_fin, i, False))
        if candidats:
            # Prend l'extrémité la PLUS éloignée de son plus proche
            # voisin : c'est un vrai BOUT de la rue, pas un point de
            # raccord intermédiaire. Inverse la logique habituelle
            # puisqu'on cherche le MAX des distances min, pas le MIN.
            candidats.sort(reverse=True)
            _, depart_idx, est_debut = candidats[0]
            inverser_depart = not est_debut

    restants: List[int] = [j for j in range(len(parties)) if j != depart_idx]
    courant: List[Tuple[float, float]] = (
        list(reversed(parties[depart_idx])) if inverser_depart else list(parties[depart_idx])
    )
    chaines: List[List[Tuple[float, float]]] = [courant]

    while restants:
        fin_actuelle = chaines[-1][-1]
        meilleur_pos: Optional[int] = None
        meilleur_dist: Optional[float] = None
        meilleur_inverser = False
        for pos, j in enumerate(restants):
            d_deb = _distance_deg(fin_actuelle, parties[j][0])
            if meilleur_dist is None or d_deb < meilleur_dist:
                meilleur_dist, meilleur_pos, meilleur_inverser = d_deb, pos, False
            d_fin = _distance_deg(fin_actuelle, parties[j][-1])
            if meilleur_dist is None or d_fin < meilleur_dist:
                meilleur_dist, meilleur_pos, meilleur_inverser = d_fin, pos, True
        j = restants.pop(meilleur_pos)
        suivant = list(reversed(parties[j])) if meilleur_inverser else list(parties[j])
        chaines.append(suivant)

    if len(chaines) > 1:
        _logger.info(
            "Géométrie de voirie : %d tronçon(s) initialement disjoint(s) "
            "(carrefours/imprécision) — réordonnés et enchaînés en une seule "
            "polyligne pour conserver un ordre de parcours cohérent.",
            len(chaines) - 1,
        )
    return [pt for ch in chaines for pt in ch]


class VoirieService:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get_polyligne_voie(self, code_insee: str, nom_voie: str) -> Optional[List[Tuple[float, float]]]:
        """Polyligne réelle (liste de `(lon, lat)`) d'une rue nommée,
        reconstruite depuis `BDTOPO_V3:voie_nommee` — `None` si la voie
        n'est pas répertoriée dans BDTOPO (chemin privé, sentier non
        officiellement nommé) : dans ce cas l'appelant doit retomber sur
        la reconstruction par adresses BAN, jamais deviné.

        Filtre `insee_commune` UNIQUEMENT côté serveur (CQL_FILTER), puis
        `nom_voie_ban` normalisé côté client — écart réel trouvé en
        investigation live (Argis, "Chemin de la Morandière") : le champ
        `nom_voie_ban` de BDTOPO stocke la partie odonyme en MAJUSCULES
        SANS ACCENT ("Chemin de la MORANDIERE"), alors que le nom transmis
        ici garde la casse/accentuation BAN d'origine ("Chemin de la
        Morandière") — un `CQL_FILTER` en égalité exacte ne matchait donc
        JAMAIS, faisant retomber silencieusement sur la reconstruction par
        adresses (bien moins fiable, voir plus haut) pour la quasi-totalité
        des rues à toponyme accentué/composé. `normaliser()` (déjà utilisé
        pour tout texte libre insensible à la casse dans ce projet) évite
        cet écart. Le nombre de voies par commune (quelques dizaines à
        quelques centaines) rend un filtrage client-side négligeable."""
        params: Dict[str, Any] = {
            "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
            "TYPENAME": "BDTOPO_V3:voie_nommee", "OUTPUTFORMAT": "application/json",
            "CQL_FILTER": f"insee_commune='{code_insee}'",
        }
        data = self._http.get_json(_WFS_BASE, params, service_key="ign_bdtopo")
        nom_norm = normaliser(nom_voie)
        features = [
            f for f in data.get("features", [])
            if normaliser(f["properties"].get("nom_voie_ban")) == nom_norm
        ]
        if not features:
            _logger.info(
                "Aucune géométrie BDTOPO pour '%s' (%s) — repli sur la reconstruction par adresses BAN.",
                nom_voie, code_insee,
            )
            return None
        parties_tuples: List[List[Tuple[float, float]]] = []
        for feature in features:
            geom = feature["geometry"]
            if geom["type"] == "LineString":
                parties = [geom["coordinates"]]
            elif geom["type"] == "MultiLineString":
                parties = geom["coordinates"]
            else:
                continue
            parties_tuples.extend([(pt[0], pt[1]) for pt in partie] for partie in parties)
        chaine = _chainer_parties(parties_tuples)
        return chaine if len(chaine) >= 2 else None

    def get_lieu_dit(self, code_insee: str, nom: str) -> Optional[Dict[str, Any]]:
        """Géométrie GeoJSON (Polygon/MultiPolygon si habité, Point si
        non habité — voir plus bas) d'un lieu-dit nommé, ou `None` s'il
        n'existe pas — décision explicite de l'utilisateur (2026-08-23) :
        repli utilisé par `main.py::decouvrir_parcelles` quand une "rue"
        tapée ne correspond à AUCUNE voie BAN, avant de conclure
        "introuvable".

        Source confirmée en direct (Arbigny, 01016) : `BDTOPO_V3:
        zone_d_habitation`, champ `toponyme` — couche SÉPARÉE de la BAN
        (adresses/voies uniquement) et de `voie_nommee` (routes), dédiée
        aux lieux-dits/hameaux HABITÉS. Champ `identifiant_voie_ban`
        (souvent vide en pratique) confirme qu'un lieu-dit n'est PAS
        forcément rattaché à une voie BAN, même quand leurs noms se
        ressemblent (écart réel trouvé : "les Blaises" à 289m de "Chemin
        des Blaises", deux entités différentes malgré le nom commun).

        Deuxième calque essayé en repli, `BDTOPO_V3:lieu_dit_non_habite`
        — écart réel trouvé en investigation live (Ambléon, 01006,
        "Corbanay", 2026-08-24) : un lieu-dit RURAL (champ/bois/lieu sans
        habitation) n'apparaît QUE dans ce calque, jamais dans
        `zone_d_habitation` ; sans ce repli, un nom comme "Corbanay"
        (explicitement signalé "Lieu Dit" par la source de l'utilisateur)
        restait faussement "introuvable". Géométrie de type Point (pas de
        contour, contrairement au premier calque) — voir
        `utils.geometrie.centroide_geometrie` et `main.py::
        _parcelles_depuis_lieu_dit` pour la gestion de ce cas.

        Comparaison par texte normalisé (accents/casse insensibles,
        comme pour `get_polyligne_voie`) — jamais de correspondance
        floue à seuil, jamais deviné. Un préfixe descriptif comme "Lieu
        Dit "/"Hameau " dans le nom saisi n'est PAS retiré automatiquement
        (même principe que "jamais deviné") : l'utilisateur doit taper le
        toponyme exact (ex: "Corbanay", pas "Lieu Dit Corbanay")."""
        nom_norm = normaliser(nom)
        for typename in ("BDTOPO_V3:zone_d_habitation", "BDTOPO_V3:lieu_dit_non_habite"):
            params: Dict[str, Any] = {
                "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
                "TYPENAME": typename, "OUTPUTFORMAT": "application/json",
                "CQL_FILTER": f"insee_commune='{code_insee}'",
            }
            data = self._http.get_json(_WFS_BASE, params, service_key="ign_bdtopo")
            for feature in data.get("features", []):
                if normaliser(feature["properties"].get("toponyme")) == nom_norm:
                    return feature["geometry"]
        return None
