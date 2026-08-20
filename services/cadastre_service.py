"""Accès aux données cadastrales (géométrie de parcelle) via
apicarto.ign.fr — voir le plan."""

from __future__ import annotations

import math
from typing import List, Optional

import config
from models.parcelle import Parcelle, normaliser_numero
from services.http_client import HttpClient
from utils.logger import get_logger

_logger = get_logger("services.cadastre_service")


def _boite_autour_du_point(lon: float, lat: float, marge_m: float) -> dict:
    """Petit polygone carré (GeoJSON) centré sur (lon, lat), de demi-côté
    `marge_m` mètres — voir `CadastreService.get_parcelles_pres_du_point`."""
    dlat = marge_m / 111320
    dlon = marge_m / (111320 * math.cos(math.radians(lat)))
    minlon, maxlon = lon - dlon, lon + dlon
    minlat, maxlat = lat - dlat, lat + dlat
    return {
        "type": "Polygon",
        "coordinates": [[
            [minlon, minlat], [maxlon, minlat], [maxlon, maxlat], [minlon, maxlat], [minlon, minlat],
        ]],
    }


class CadastreService:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def get_parcelle(
        self, code_insee: str, section: str, numero, *,
        commune: str = "", departement: str = "", code_postal: str = "", rue: str = "",
    ) -> List[Parcelle]:
        """Géométrie d'une parcelle identifiée par section+numéro.
        `numero` accepte n'importe quel format (entier brut ou chaîne
        zéro-remplie, voir `normaliser_numero`) — normalisé avant
        l'appel puisque apicarto exige 4 chiffres exactement (confirmé
        en investigation live). Renvoie une liste (généralement 0 ou 1
        élément ; l'API elle-même est en liste, jamais fusionnée ici).

        `commune`/`departement`/`code_postal`/`rue` : contexte connu de
        l'appelant (l'`ElementTravail` en cours), assemblé directement
        dans les `Parcelle` renvoyées plutôt que redemandé à l'API, qui
        ne renvoie que `nom_com`/`code_dep`, pas le département à 2
        chiffres ni le code postal ni la rue."""
        numero_norm = normaliser_numero(numero)
        url = f"{config.APICARTO_BASE}/cadastre/parcelle"
        params = {"code_insee": code_insee, "section": section, "numero": numero_norm}
        data = self._http.get_json(url, params, service_key="cadastre")
        features = data.get("features", [])
        return [
            Parcelle(
                code_insee=code_insee, section=section, numero=numero_norm,
                commune=commune, departement=departement, code_postal=code_postal, rue=rue,
                geometry=f["geometry"],
            )
            for f in features
        ]

    def get_parcelles_pres_du_point(
        self, code_insee: str, lon: float, lat: float, *,
        commune: str = "", departement: str = "", code_postal: str = "", rue: str = "",
        marge_m: float = 8.0,
    ) -> List[Parcelle]:
        """Parcelle(s) proche(s) d'un point donné (ex: un point d'adresse
        BAN) — utilise un petit polygone tampon plutôt qu'un point exact,
        confirmé nécessaire en investigation live : un point d'adresse
        BAN ne tombe pas toujours À L'INTÉRIEUR de sa parcelle cadastrale
        (sources/relevés différents entre la BAN et le PCI, écart
        constaté même sur une adresse réelle proche du centre d'une
        petite parcelle résidentielle). Peut renvoyer plusieurs
        candidates si le point est proche d'une limite de parcelle —
        c'est à l'appelant de désambiguïser (ex: la plus proche du point
        d'origine), jamais deviné ici."""
        geom = _boite_autour_du_point(lon, lat, marge_m)
        url = f"{config.APICARTO_BASE}/cadastre/parcelle"
        import json
        params = {"code_insee": code_insee, "geom": json.dumps(geom)}
        data = self._http.get_json(url, params, service_key="cadastre")
        features = data.get("features", [])
        return [
            Parcelle(
                code_insee=code_insee, section=f["properties"]["section"],
                numero=f["properties"]["numero"],
                commune=commune, departement=departement, code_postal=code_postal, rue=rue,
                geometry=f["geometry"],
            )
            for f in features
        ]

    def get_parcelles_section(self, code_insee: str, section: str, *, limit: int = 1000) -> List[dict]:
        """Toutes les parcelles brutes (features GeoJSON, pas encore de
        `Parcelle`) d'une section — utile pour la découverte le long
        d'une rue quand on connaît déjà la/les sections concernées (voir
        services/traversal_service.py), évite un appel par numéro."""
        url = f"{config.APICARTO_BASE}/cadastre/parcelle"
        params = {"code_insee": code_insee, "section": section, "_limit": limit}
        data = self._http.get_json(url, params, service_key="cadastre")
        return data.get("features", [])
