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

_logger = get_logger("services.voirie_service")

_WFS_BASE = "https://data.geopf.fr/wfs/ows"
_EPSILON_DEGRES = 1e-7  # tolérance pour considérer 2 points comme identiques


def _chainer_parties(parties: List[List[Tuple[float, float]]]) -> List[Tuple[float, float]]:
    """Chaîne des tronçons de LineString déconnectés en UNE polyligne
    continue, en accolant bout à bout par proximité d'extrémité. Les
    tronçons qui ne se raccrochent à rien restent ignorés (voie en
    plusieurs branches distinctes) — jamais fusionnés au hasard."""
    if not parties:
        return []

    def proche(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
        return abs(a[0] - b[0]) < _EPSILON_DEGRES and abs(a[1] - b[1]) < _EPSILON_DEGRES

    restantes = [list(p) for p in parties]
    chaine = restantes.pop(0)
    progres = True
    while restantes and progres:
        progres = False
        for i, partie in enumerate(restantes):
            if proche(chaine[-1], partie[0]):
                chaine.extend(partie[1:])
            elif proche(chaine[-1], partie[-1]):
                chaine.extend(list(reversed(partie))[1:])
            elif proche(chaine[0], partie[-1]):
                chaine = partie[:-1] + chaine
            elif proche(chaine[0], partie[0]):
                chaine = list(reversed(partie))[:-1] + chaine
            else:
                continue
            restantes.pop(i)
            progres = True
            break
    if restantes:
        _logger.warning(
            "Géométrie de voirie : %d tronçon(s) non connecté(s) au reste, ignoré(s) "
            "(voie possiblement en plusieurs branches distinctes).", len(restantes),
        )
    return chaine


class VoirieService:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get_polyligne_voie(self, code_insee: str, nom_voie: str) -> Optional[List[Tuple[float, float]]]:
        """Polyligne réelle (liste de `(lon, lat)`) d'une rue nommée,
        reconstruite depuis `BDTOPO_V3:voie_nommee` — `None` si la voie
        n'est pas répertoriée dans BDTOPO (chemin privé, sentier non
        officiellement nommé, faute de frappe entre le nom BAN et le nom
        utilisé dans le fichier de travail) : dans ce cas l'appelant doit
        retomber sur la reconstruction par adresses BAN, jamais deviné."""
        nom_echappe = nom_voie.replace("'", "''")
        params: Dict[str, Any] = {
            "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
            "TYPENAME": "BDTOPO_V3:voie_nommee", "OUTPUTFORMAT": "application/json",
            "CQL_FILTER": f"insee_commune='{code_insee}' AND nom_voie_ban='{nom_echappe}'",
        }
        data = self._http.get_json(_WFS_BASE, params, service_key="ign_bdtopo")
        features = data.get("features", [])
        if not features:
            _logger.info(
                "Aucune géométrie BDTOPO pour '%s' (%s) — repli sur la reconstruction par adresses BAN.",
                nom_voie, code_insee,
            )
            return None
        geom = features[0]["geometry"]
        if geom["type"] == "LineString":
            parties = [geom["coordinates"]]
        elif geom["type"] == "MultiLineString":
            parties = geom["coordinates"]
        else:
            return None
        parties_tuples = [[(pt[0], pt[1]) for pt in partie] for partie in parties]
        chaine = _chainer_parties(parties_tuples)
        return chaine if len(chaine) >= 2 else None
