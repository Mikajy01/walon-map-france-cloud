"""Accès à la couche WFS SANDRE `sa:SysTraitementEauxUsees_FXX` (Système
de Traitement des Eaux Usées / stations d'épuration) — alternative
trouvée en recherche web (2026-08-24) pour la colonne "Stations
d'épuration" du nouveau gabarit, laissée sans source connue lors de la
première passe (`installations_classees`/DU/SUP ne couvraient pas ce
concept, voir config.ROLES_SANS_REGLE).

Endpoint trouvé via le catalogue SIGENA (fiche du service géographique
du référentiel SANDRE des stations de traitement des eaux usées),
CONFIRMÉ en direct : GetFeature réel sur une zone connue (Lyon) renvoie
une vraie station ("CHAPONOST", `LbTypeOuvrageDepollution` = "Station
d'assainissement").

Même ordre d'axes que services/wfs_remnappe_service.py (latitude,
longitude) pour `urn:ogc:def:crs:EPSG::4326` — confirmé en direct
(bbox Lyon, résultat dans l'enveloppe correcte).

`_FXX` = France métropolitaine (le service SANDRE expose aussi des
variantes DOM : `_GLP`/`_MTQ`/`_GUF`/`_REU`/`_MYT` — non câblées ici,
aucun besoin réel constaté sur ce projet)."""

from __future__ import annotations

import math
from typing import Optional

from services.http_client import HttpClient
from utils.logger import get_logger

_logger = get_logger("services.wfs_steu_service")

_WFS_BASE = "https://services.sandre.eaufrance.fr/geo/odp"


class WfsSteuService:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    @staticmethod
    def _bbox(lat: float, lon: float, marge_m: float = 5.0) -> str:
        dlat = marge_m / 111320
        dlon = marge_m / (111320 * math.cos(math.radians(lat)))
        return f"{lat - dlat},{lon - dlon},{lat + dlat},{lon + dlon},urn:ogc:def:crs:EPSG::4326"

    def existe(self, lat: float, lon: float) -> Optional[str]:
        """"Stations d'épuration" — présence/absence, pas de champ à
        filtrer (même mécanisme que `WfsRemnappeService.eaip`)."""
        params = {
            "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
            "TYPENAMES": "sa:SysTraitementEauxUsees_FXX", "BBOX": self._bbox(lat, lon),
        }
        try:
            xml = self._http.get_text(_WFS_BASE, params, service_key="sandre_steu_wfs")
        except Exception as exc:  # noqa: BLE001 — une couche indisponible ne doit jamais faire échouer tout le traitement de la parcelle
            _logger.warning("Couche SysTraitementEauxUsees indisponible (lat=%s, lon=%s) : %s", lat, lon, exc)
            return None
        return "O" if "<wfs:member>" in xml else "N"
