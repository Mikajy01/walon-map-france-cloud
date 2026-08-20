"""Accès à la CLPA (Carte de Localisation des Phénomènes d'Avalanche) via
le GeoServer public d'INRAE — service DIFFÉRENT de Géorisques (autre
fournisseur, autre domaine), découvert en investigation live après que
la seule source jusqu'ici référencée (Cartorisque, prim.net) se soit
révélée décommissionnée (HTTP 403).

Trouvé en inspectant les appels réseau embarqués dans la page du
visualiseur public `https://map.avalanches.fr/` (recherche du texte
"geoserver"/"clpa" dans le HTML/JS de la page) — endpoint confirmé en
direct (`GetCapabilities` HTTP 200, couches `siavalanches:clpa_zont`/
`clpa_zonpi` listées) et testé positivement sur une zone réelle connue
(Val d'Isère, Savoie) avant d'être utilisé sur une commune cible.

Deux couches confirmées et mappées à 2 des 3 colonnes du gabarit :
  - `clpa_zont` ("zone témoignage") : champ `SOURCE` réel observé
    incluant `"tem"` (témoignage) — correspond à "Témoignages
    d'avalanches".
  - `clpa_zonpi` ("zone photo-interprétation") : correspond à
    "Interprétation des phénomène passés".
La 3e colonne du gabarit ("Zones sans enquête terrain") n'a PAS de
couche CLPA correspondante identifiée (aucune couche "enquête" trouvée
dans le catalogue WFS de ce serveur) — non câblée, volontairement, tant
que sa définition méthodologique exacte n'est pas confirmée.

PAS le même ordre d'axes que le WFS Géorisques (voir wfs_georisques_
service.py) : ce serveur utilise l'ordre standard (longitude, latitude)
pour son `bbox` — confirmé en direct (résultats réels obtenus avec cet
ordre sur Val d'Isère), pas d'inversion ici."""

from __future__ import annotations

import re
from typing import Optional

from services.http_client import HttpClient
from utils.logger import get_logger

_logger = get_logger("services.wfs_clpa_service")

_WFS_BASE = "https://carto-service.inrae.fr/geoserver/siavalanches/ows"
_RE_NUMBER_RETURNED = re.compile(r'"totalFeatures":\s*(\d+)')


class WfsClpaService:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    @staticmethod
    def _bbox(lat: float, lon: float, marge_deg: float = 0.0005) -> str:
        """~50m de tampon (en degrés, approximatif mais suffisant pour un
        test d'existence ponctuel) — ordre (longitude, latitude),
        `EPSG:4326`."""
        return f"{lon - marge_deg},{lat - marge_deg},{lon + marge_deg},{lat + marge_deg},EPSG:4326"

    def _existe(self, layer: str, lat: float, lon: float) -> Optional[str]:
        """`"O"`/`"N"` selon qu'au moins un élément de `layer` intersecte
        un petit tampon autour du point, `None` si la réponse n'est pas
        exploitable (jamais deviné)."""
        params = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeName": f"siavalanches:{layer}", "outputFormat": "application/json",
            "bbox": self._bbox(lat, lon), "count": 1,
        }
        try:
            texte = self._http.get_text(_WFS_BASE, params, service_key="clpa_wfs")
        except Exception as exc:  # noqa: BLE001 — une couche indisponible ne doit jamais faire échouer tout le traitement de la parcelle
            _logger.warning("Couche CLPA '%s' indisponible (lat=%s, lon=%s) : %s", layer, lat, lon, exc)
            return None
        m = _RE_NUMBER_RETURNED.search(texte)
        if not m:
            _logger.warning(
                "Couche CLPA '%s' (lat=%s, lon=%s) : réponse sans 'totalFeatures' exploitable — "
                "extrait : %s", layer, lat, lon, texte[:200],
            )
            return None
        return "O" if int(m.group(1)) > 0 else "N"

    def temoignage(self, lat: float, lon: float) -> Optional[str]:
        """"Témoignages d'avalanches" — couche `clpa_zont`."""
        return self._existe("clpa_zont", lat, lon)

    def interpretation(self, lat: float, lon: float) -> Optional[str]:
        """"Interprétation des phénomène passés" — couche `clpa_zonpi`."""
        return self._existe("clpa_zonpi", lat, lon)
