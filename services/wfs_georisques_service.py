"""Accès aux couches WFS Géorisques (aléa inondation TRI, ouvrages de
protection) — service DIFFÉRENT des APIs REST JSON déjà utilisées
(`georisques_service.py`) : protocole WFS 2.0/GML, découvert en
cherchant une source pour le bloc "Inondation (Aléa...)" (12 colonnes)
après avoir confirmé que l'API REST v1 ne les couvre pas (schéma
`AziModel` sans champ par parcelle).

Endpoint de base trouvé via la page `/services` du site (mentionnée
dans sa documentation publique) : `https://www.georisques.gouv.fr/
services` (MapServer WFS), capacités récupérées via `GetCapabilities`.

PIÈGE RÉEL trouvé en construisant ce module : WFS 2.0 + CRS EPSG:4326
utilise l'ordre (latitude, longitude) pour un `bbox`, PAS (longitude,
latitude) comme la plupart des autres APIs de ce projet — confirmé en
direct (0 résultat avec l'ordre lon,lat sur une zone connue pour avoir
des données réelles — le TRI de la Vilaine ; résultats réels dès
l'inversion de l'ordre).

Mapping type d'aléa -> préfixe de couche confirmé en direct sur deux
zones réelles connues : `01` = débordement de cours d'eau (testé sur le
TRI Vilaine, `cours_deau: "LA VILAINE"`), `03` = submersion marine
(testé sur le TRI La Rochelle Île de Ré, explicitement nommé "Alea
submersion marine"), `02` = ruissellement par élimination (le seul des
3 aléas de la méthodologie TRI/COVADIS restant). Confirmé cohérent
structurellement : le nombre de variantes d'intensité disponibles par
type (débordement: 4, submersion: 4 dont la variante changement
climatique, ruissellement: 3 sans variante climatique) correspond
EXACTEMENT au nombre de colonnes réelles par groupe dans le gabarit."""

from __future__ import annotations

import math
import re
import time
from typing import Optional

import requests

from services.http_client import HttpClient
from utils.logger import get_logger

_logger = get_logger("services.wfs_georisques_service")

_WFS_BASE = "https://www.georisques.gouv.fr/services"
_RE_MEMBER = re.compile(r"<wfs:member>", re.S)
_RE_NUMBER_RETURNED = re.compile(r'numberReturned="(\d+)"')

# Ré-essais LOCAUX sur un 404 précis de CE service — exception délibérée
# à la règle générale (`utils/retry.py::_est_reessayable`, confirmée
# ailleurs par l'incident PASH côté wallon) selon laquelle un 4xx est
# définitif et ne doit jamais être réessayé. Écart réel confirmé en
# direct sur CE serveur précis : la MÊME requête (mêmes paramètres,
# couche connue pour exister) a renvoyé un 404 lors d'un run réel, puis
# un 200 avec réponse valide quelques minutes plus tard — donc un panne
# transitoire côté serveur WFS Géorisques, pas une ressource absente.
_TENTATIVES_404 = 3
_DELAI_ENTRE_TENTATIVES_S = 3.0


class WfsGeorisquesService:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    @staticmethod
    def _bbox(lat: float, lon: float, marge_m: float = 5.0) -> str:
        """`"lat_min,lon_min,lat_max,lon_max,EPSG:4326"` — ordre
        (latitude, longitude), voir l'avertissement du docstring de
        module."""
        dlat = marge_m / 111320
        dlon = marge_m / (111320 * math.cos(math.radians(lat)))
        return f"{lat - dlat},{lon - dlon},{lat + dlat},{lon + dlon},EPSG:4326"

    def _existe(self, layer: str, lat: float, lon: float) -> Optional[str]:
        """`"O"`/`"N"` selon qu'au moins un élément de `layer` intersecte
        un petit tampon autour du point, `None` si la réponse n'est pas
        exploitable (jamais deviné — voir le principe général du projet)."""
        params = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeName": f"ms:{layer}", "bbox": self._bbox(lat, lon), "count": 1,
        }
        xml: Optional[str] = None
        derniere_exception: Optional[Exception] = None
        for tentative in range(1, _TENTATIVES_404 + 1):
            try:
                xml = self._http.get_text(_WFS_BASE, params, service_key="georisques_wfs")
                break
            except requests.exceptions.HTTPError as exc:
                derniere_exception = exc
                if exc.response is None or exc.response.status_code != 404 or tentative == _TENTATIVES_404:
                    break
                _logger.warning(
                    "Couche WFS '%s' (lat=%s, lon=%s) : 404 transitoire confirmé sur ce serveur "
                    "(tentative %d/%d), nouvel essai dans %.0fs.",
                    layer, lat, lon, tentative, _TENTATIVES_404, _DELAI_ENTRE_TENTATIVES_S,
                )
                time.sleep(_DELAI_ENTRE_TENTATIVES_S)
            except Exception as exc:  # noqa: BLE001 — une couche WFS indisponible ne doit jamais faire échouer tout le traitement de la parcelle
                derniere_exception = exc
                break
        if xml is None:
            # Écart réel trouvé en investigation live : ce `except` était
            # totalement silencieux (aucun log), ce qui a fait perdre la
            # trace d'une vraie panne Géorisques touchant les 14 couches
            # WFS sur tout un lot (147 parcelles) sans qu'aucune erreur
            # n'apparaisse nulle part — seul le compteur de repli "N"
            # journalisé (`cellules_a_revisiter.csv`) l'a révélé après
            # coup. Toujours logger, même si la valeur reste `None`.
            _logger.warning(
                "Couche WFS '%s' indisponible (lat=%s, lon=%s) : %s", layer, lat, lon, derniere_exception,
            )
            return None
        m = _RE_NUMBER_RETURNED.search(xml)
        if not m:
            _logger.warning(
                "Couche WFS '%s' (lat=%s, lon=%s) : réponse sans 'numberReturned' exploitable — "
                "extrait : %s", layer, lat, lon, xml[:200],
            )
            return None
        return "O" if int(m.group(1)) > 0 else "N"

    # -- aléa inondation, 3 types × intensités (voir docstring module) --

    def alea_debordement(self, lat: float, lon: float, intensite: str) -> Optional[str]:
        return self._existe(f"ALEA_SYNT_01_{intensite}_FXX", lat, lon)

    def alea_ruissellement(self, lat: float, lon: float, intensite: str) -> Optional[str]:
        return self._existe(f"ALEA_SYNT_02_{intensite}_FXX", lat, lon)

    def alea_submersion(self, lat: float, lon: float, intensite: str) -> Optional[str]:
        return self._existe(f"ALEA_SYNT_03_{intensite}_FXX", lat, lon)

    # -- ouvrages / zonage TRI --------------------------------------

    def territoire_risque_important(self, lat: float, lon: float) -> Optional[str]:
        return self._existe("LIMITETRI_FXX", lat, lon)

    def ouvrage_protection(self, lat: float, lon: float) -> Optional[str]:
        return self._existe("OUV_PROTECTION_FXX", lat, lon)

    def zone_sur_alea(self, lat: float, lon: float) -> Optional[str]:
        """Zone de sur-aléa (derrière un ouvrage de protection, en cas
        de rupture) — `OUV_ZONSALEA_FXX`."""
        return self._existe("OUV_ZONSALEA_FXX", lat, lon)

    def zone_soustraite_alea(self, lat: float, lon: float) -> Optional[str]:
        """Zone soustraite à l'aléa grâce à un ouvrage de protection —
        `OUV_ZONSSINOND_FXX`."""
        return self._existe("OUV_ZONSSINOND_FXX", lat, lon)
