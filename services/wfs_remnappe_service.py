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
from utils.logger import get_logger

_logger = get_logger("services.wfs_remnappe_service")

_WFS_BASE = "https://mapsref.brgm.fr/wxs/georisques/risques"
_RE_MEMBER = re.compile(r"<wfs:member>(.*?)</wfs:member>", re.S)
_RE_CLASSE = re.compile(r"<ms:classe>([^<]*)</ms:classe>")
_RE_FIAB_TOT = re.compile(r"<ms:fiab_tot>([^<]*)</ms:fiab_tot>")

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
