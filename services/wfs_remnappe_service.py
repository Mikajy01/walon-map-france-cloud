"""Accès à la couche WFS BRGM `REMNAPPE_FIAB` (banque inondations /
remontées de nappes, niveau de fiabilité) — service DIFFÉRENT de
Géorisques (autre fournisseur, `mapsref.brgm.fr`), découvert en
cherchant une source réelle pour les colonnes "Zones potentiellement
sujettes aux débordements de nappe/inondations de cave fiabilité
FORTE/MOYENNE/FAIBLE/INCONNUE" du nouveau gabarit (2026-08-24) — le
champ `remonteeNappe.specifique` de l'API REST Géorisques (déjà
câblée, voir `georisques_service.py::get_resultats_rapport_risque`)
est resté `null` sur 4 points réels très différents, confirmant qu'il
ne porte PAS cette information.

Trouvé via recherche web puis confirmé en direct sur `GetCapabilities` :
titre officiel "Zones sensibles aux remontées de nappes avec prise en
compte du niveau de fiabilité". Champs réels observés (Saint-Vulbas,
01390, feature `REMNAPPE_FIAB.29505`) :
  - `classe` : exactement 3 valeurs, confirmées sur ~500 features
    réparties sur toute la France — "Zones potentiellement sujettes aux
    débordements de nappe" / "Zones potentiellement sujettes aux
    inondations de cave" / "Pas de débordement de nappe ni
    d'inondation de cave" — correspondance EXACTE (mot pour mot) avec
    3 des groupes de colonnes du nouveau gabarit.
  - `fiab_tot` : exactement 3 valeurs sur le même échantillon — FORTE/
    MOYENNE/FAIBLE. Aucune valeur "INCONNUE" jamais observée — traité
    comme le champ ABSENT (une feature dont la fiabilité totale n'a
    pas pu être calculée), jamais deviné comme une 4e valeur littérale
    qui n'existe peut-être pas.

PIÈGE : même serveur MapServer que `wfs_georisques_service.py`
(msWFSGetFeature) — GML uniquement (JSON refusé, confirmé HTTP 400),
et bbox en ordre (latitude, longitude) pour `urn:ogc:def:crs:EPSG::4326`
(confirmé en direct : 0 résultat en ordre lon,lat sur une zone connue
pour avoir des données réelles, résultats réels dès l'inversion)."""

from __future__ import annotations

import html
import math
import re
from typing import Optional

from services.http_client import HttpClient
from utils.geometrie import point_dans_geometrie
from utils.logger import get_logger

_logger = get_logger("services.wfs_remnappe_service")

_WFS_BASE = "https://mapsref.brgm.fr/wxs/georisques/risques"
_RE_MEMBER = re.compile(r"<wfs:member>(.*?)</wfs:member>", re.S)
_RE_CLASSE = re.compile(r"<ms:classe>([^<]*)</ms:classe>")
_RE_FIAB_TOT = re.compile(r"<ms:fiab_tot>([^<]*)</ms:fiab_tot>")
_RE_POSLIST = re.compile(r"<gml:posList[^>]*>([^<]+)</gml:posList>")


def _point_dans_reponse_gml(lat: float, lon: float, xml: str) -> bool:
    """True si `(lat, lon)` tombe dans AU MOINS UN des anneaux de
    polygone d'une réponse GML — nécessaire car ce serveur (MapServer)
    NE FILTRE PAS par géométrie exacte sur son paramètre `BBOX` pour au
    moins certaines couches à géométrie complexe. Bug réel trouvé en
    investigation live (La Boisse, 01049, "Chemin de la Saccunière",
    2026-08-27, signalé par l'utilisateur : la carte georisques.gouv.fr
    ne montre AUCUNE zone à cet endroit précis, alors que `eaip()`
    répondait "O") : une requête `BBOX` de ~50m x 50m autour de la
    parcelle renvoyait quand même la TOTALITÉ de la géométrie `MASQ_
    EAIP` (1 seule feature, 1104 anneaux de polygone dispersés sur tout
    le département, enveloppe globale 45.61-46.34 / 4.92-5.99) — le
    filtre BBOX ne teste que l'enveloppe GLOBALE de la feature, jamais
    ses anneaux individuels. `"<wfs:member>" in xml` (utilisé jusqu'ici)
    ne prouve donc RIEN sur le point précis interrogé pour ce genre de
    couche — seul un vrai test géométrique anneau par anneau (voir
    `utils/geometrie.py::point_dans_geometrie`, déjà utilisé ailleurs
    dans ce projet pour la même raison) donne une réponse fiable."""
    for bloc in _RE_POSLIST.findall(xml):
        nombres = [float(x) for x in bloc.split()]
        # Ordre (latitude, longitude) dans le posList, comme partout sur
        # ce serveur (voir l'avertissement du docstring de module) —
        # converti en [longitude, latitude] pour `point_dans_geometrie`
        # (convention GeoJSON, déjà celle utilisée par cette fonction).
        anneau = [[nombres[i + 1], nombres[i]] for i in range(0, len(nombres) - 1, 2)]
        if len(anneau) < 3:
            continue
        geometry = {"type": "Polygon", "coordinates": [anneau]}
        if point_dans_geometrie(lon, lat, geometry):
            return True
    return False

CLASSE_DEBORDEMENT_NAPPE = "Zones potentiellement sujettes aux débordements de nappe"
CLASSE_INONDATION_CAVE = "Zones potentiellement sujettes aux inondations de cave"
CLASSE_AUCUN_RISQUE = "Pas de débordement de nappe ni d'inondation de cave"


class WfsRemnappeService:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    @staticmethod
    def _bbox(lat: float, lon: float, marge_m: float = 5.0) -> str:
        """Ordre (latitude, longitude), voir l'avertissement du docstring
        de module — même piège que `wfs_georisques_service.py`."""
        dlat = marge_m / 111320
        dlon = marge_m / (111320 * math.cos(math.radians(lat)))
        return f"{lat - dlat},{lon - dlon},{lat + dlat},{lon + dlon},EPSG:4326"

    def eaip(self, lat: float, lon: float) -> Optional[str]:
        """"Remontée de nappes (Enveloppes Approchées des Inondations
        Potentielles en cours d'eau et submersion marine de plus d'un
        hectare)" — couche `MASQ_EAIP`, même serveur BRGM que
        `REMNAPPE_FIAB`. Titre officiel confirmé en direct via
        `GetCapabilities` : correspondance EXACTE (mot pour mot) avec
        cette colonne du nouveau gabarit.

        Test géométrique RÉEL (voir `_point_dans_reponse_gml`) — jamais
        juste "une réponse est revenue", depuis le bug réel trouvé en
        investigation live (2026-08-27) : le filtre `BBOX` de ce serveur
        ne teste que l'enveloppe globale de la géométrie `MASQ_EAIP`
        (une SEULE feature réelle, 1104 anneaux dispersés sur tout le
        département), donc répondait "O" pour N'IMPORTE QUEL point du
        département, y compris des parcelles réellement hors de toute
        zone visible sur la carte officielle (confirmé faux en direct,
        La Boisse, "Chemin de la Saccunière")."""
        params = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeName": "ms:MASQ_EAIP", "bbox": self._bbox(lat, lon),
        }
        try:
            xml = self._http.get_text(_WFS_BASE, params, service_key="brgm_remnappe_wfs")
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Couche MASQ_EAIP indisponible (lat=%s, lon=%s) : %s", lat, lon, exc)
            return None
        return "O" if _point_dans_reponse_gml(lat, lon, xml) else "N"

    def masque_etude_specifique(self, lat: float, lon: float) -> Optional[str]:
        """"Remontée de nappes (Masque étude spécifique en cours)" —
        couche `MASQ_AFFLEUR`, même serveur BRGM que `REMNAPPE_FIAB`/
        `MASQ_EAIP`/`MASQ_BDLISA`. Titre officiel confirmé en direct via
        `GetCapabilities` : correspondance EXACTE (mot pour mot) avec
        cette colonne du nouveau gabarit.

        Même correctif géométrique que `eaip` (2026-08-27) : ce serveur
        ne filtre pas par géométrie exacte sur `BBOX`, un simple
        `"<wfs:member>" in xml` n'aurait jamais prouvé que le POINT
        précis interrogé est réellement dans la zone."""
        params = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeName": "ms:MASQ_AFFLEUR", "bbox": self._bbox(lat, lon),
        }
        try:
            xml = self._http.get_text(_WFS_BASE, params, service_key="brgm_remnappe_wfs")
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Couche MASQ_AFFLEUR indisponible (lat=%s, lon=%s) : %s", lat, lon, exc)
            return None
        return "O" if _point_dans_reponse_gml(lat, lon, xml) else "N"

    def classe_fiabilite(self, lat: float, lon: float, classe: str, fiabilite: Optional[str]) -> Optional[str]:
        """`"O"`/`"N"` selon qu'au moins une feature au point donné
        matche à la fois `classe` (voir les 3 constantes du module) et
        `fiabilite` (`"FORTE"`/`"MOYENNE"`/`"FAIBLE"`, ou `None` pour
        "INCONNUE" = champ `fiab_tot` absent de la feature). `None` si
        la réponse n'est pas exploitable (jamais deviné)."""
        params = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeName": "ms:REMNAPPE_FIAB", "bbox": self._bbox(lat, lon),
        }
        try:
            xml = self._http.get_text(_WFS_BASE, params, service_key="brgm_remnappe_wfs")
        except Exception as exc:  # noqa: BLE001 — une couche indisponible ne doit jamais faire échouer tout le traitement de la parcelle
            _logger.warning("Couche REMNAPPE_FIAB indisponible (lat=%s, lon=%s) : %s", lat, lon, exc)
            return None
        for bloc in _RE_MEMBER.findall(xml):
            m_classe = _RE_CLASSE.search(bloc)
            # `html.unescape` : écart réel trouvé en investigation live
            # (2026-08-24) — le GML renvoyé par ce serveur MapServer
            # échappe l'apostrophe en entité XML (`d&#39;inondation`),
            # une comparaison directe contre la constante Python (avec
            # une vraie apostrophe) ne matchait donc JAMAIS, silencieusement.
            if not m_classe or html.unescape(m_classe.group(1)) != classe:
                continue
            m_fiab = _RE_FIAB_TOT.search(bloc)
            fiab_observee = html.unescape(m_fiab.group(1)) if m_fiab else None
            if fiab_observee == fiabilite:
                return "O"
        return "N"
