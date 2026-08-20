"""Géocodage IGN (BAN — Base Adresse Nationale) — recherche d'une rue,
adresses le long d'une rue, filtrage par polygone. Voir le plan.

Stratégie de découverte confirmée en investigation live (l'API n'offre
PAS de recherche directe "toutes les adresses de cette rue par nom" —
`search?type=housenumber&q=<nom de rue>` renvoie systématiquement une
liste vide) :
    1. `search?type=street` sur le nom de rue -> point centroïde + `id`
       BAN de la rue (`{code_insee}_{voie_id}`).
    2. `reverse?type=housenumber` autour de ce centroïde, avec un rayon
       large -> toutes les adresses proches, filtrées ensuite par
       préfixe `voie_id` (des adresses de rues voisines apparaissent
       aussi au-delà d'une certaine distance, jamais mélangées par
       erreur grâce à ce filtre)."""

from __future__ import annotations

from typing import List, Optional

import requests

import config
from models.adresse import AdressePoint
from services.http_client import HttpClient
from utils.geometrie import point_dans_geometrie
from utils.logger import get_logger

_logger = get_logger("services.geocodage_service")

# Nombre de résultats demandés à `reverse` — 50 est le MAXIMUM accepté
# par l'API (confirmé : `limit=100` renvoie HTTP 400 "must be an integer
# between 1 and 50"), déjà large marge au-dessus du nombre d'adresses
# attendu sur une rue résidentielle (confirmé : 27 parcelles sur "Rue du
# Lardon", 11 adresses distinctes trouvées dans un rayon de 67m).
_REVERSE_LIMIT = 50


class GeocodageService:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def rechercher_rue(self, rue: str, code_insee: str) -> Optional[dict]:
        """Point centroïde + identifiant BAN d'une rue, ou `None` si
        introuvable. Renvoie `{"voie_id": str, "lon": float, "lat": float}`."""
        url = f"{config.GEOCODAGE_BASE}/search"
        params = {"q": rue, "citycode": code_insee, "type": "street", "limit": 1}
        try:
            data = self._http.get_json(url, params, service_key="geocodage")
        except requests.exceptions.HTTPError as exc:
            # Une "voie" mal formée (guillemets littéraux dans le nom
            # lui-même, ex: `Zone artisanale "les Prés d'ARGIS"`, un vrai
            # nom trouvé en investigation live via `CommuneService.
            # lister_voies` sur Argis) fait renvoyer HTTP 400 par l'API de
            # recherche — jamais transitoire, jamais résolu par un
            # réessai. Sans ce garde-fou, une SEULE voie mal formée
            # plantait tout `traiter_commune_complete` en découverte
            # automatique (aucun try/except autour de l'appel par rue),
            # perdant le traitement de toutes les rues restantes de la
            # liste alors que le budget de temps était loin d'être atteint.
            # Traité comme "introuvable", jamais deviné.
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                _logger.warning(
                    "Rue introuvable dans la BAN (requête rejetée, HTTP %d) : '%s' (code_insee=%s)",
                    exc.response.status_code, rue, code_insee,
                )
                return None
            raise
        features = data.get("features", [])
        if not features:
            _logger.warning("Rue introuvable dans la BAN : '%s' (code_insee=%s)", rue, code_insee)
            return None
        feat = features[0]
        ban_id = feat["properties"]["id"]  # "{code_insee}_{voie_id}"
        parts = ban_id.split("_")
        voie_id = parts[1] if len(parts) >= 2 else ""
        lon, lat = feat["geometry"]["coordinates"]
        return {"voie_id": voie_id, "lon": lon, "lat": lat}

    def reverse(self, lon: float, lat: float, *, limit: int = _REVERSE_LIMIT) -> List[AdressePoint]:
        url = f"{config.GEOCODAGE_BASE}/reverse"
        params = {"lon": lon, "lat": lat, "type": "housenumber", "index": "address", "limit": limit}
        data = self._http.get_json(url, params, service_key="geocodage")
        points = []
        for feat in data.get("features", []):
            props = feat["properties"]
            plon, plat = feat["geometry"]["coordinates"]
            points.append(AdressePoint(
                id=props["id"], housenumber=props["housenumber"], street=props["street"],
                lon=plon, lat=plat,
            ))
        return points

    def adresses_pour_rue(self, rue: str, code_insee: str) -> List[AdressePoint]:
        """Toutes les adresses BAN trouvées pour une rue précise —
        combine `rechercher_rue` + `reverse`, filtré par `voie_id` pour
        exclure les adresses de rues voisines que `reverse` peut
        renvoyer au-delà d'une certaine distance."""
        rue_info = self.rechercher_rue(rue, code_insee)
        if rue_info is None:
            return []
        tous_points = self.reverse(rue_info["lon"], rue_info["lat"])
        return [p for p in tous_points if p.voie_id == rue_info["voie_id"]]

    @staticmethod
    def points_dans_polygone(points: List[AdressePoint], polygon: dict) -> List[AdressePoint]:
        """Filtre les points d'adresse dont les coordonnées tombent dans
        un polygone GeoJSON (géométrie de parcelle) — implémentation
        minimale (ray casting) sans dépendance externe (pas de shapely
        dans requirements.txt), suffisante pour un point contre un
        polygone simple (pas de trous, ce qui est le cas des parcelles
        cadastrales confirmées en investigation live : MultiPolygon à un
        seul anneau extérieur)."""
        resultat = []
        for point in points:
            if point_dans_geometrie(point.lon, point.lat, polygon):
                resultat.append(point)
        return resultat
