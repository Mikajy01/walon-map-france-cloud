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

    def get_parcelles_dans_geometrie(
        self, code_insee: str, geometry: dict, *,
        commune: str = "", departement: str = "", code_postal: str = "", rue: str = "",
    ) -> List[Parcelle]:
        """Parcelle(s) intersectant une géométrie GeoJSON arbitraire
        (polygone ou multipolygone) — contrairement à `get_parcelles_
        pres_du_point`, qui construit lui-même un petit tampon carré
        autour d'un POINT, ici l'appelant fournit directement sa propre
        géométrie (ex: le polygone d'un lieu-dit BDTOPO, voir
        `main.py::_parcelles_depuis_lieu_dit`)."""
        url = f"{config.APICARTO_BASE}/cadastre/parcelle"
        import json
        params = {"code_insee": code_insee, "geom": json.dumps(geometry)}
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
        services/traversal_service.py), évite un appel par numéro.

        Pagine via `_start`/`_limit` (confirmé en direct : APIcarto les
        supporte tous les deux) jusqu'à épuisement — écart réel trouvé
        en investigation live (Buellas, 2026-09-02, section 0B) : un
        seul appel `_limit=1000` tronquait SILENCIEUSEMENT une section
        de 1166 parcelles réelles, sans aucune erreur ni avertissement.
        Les 166 parcelles manquantes (dont plusieurs bordières
        confirmées d'"Impasse des Tulipes", jamais adressées donc
        jamais trouvées par l'autre voie de découverte) étaient donc
        invisibles pour TOUTE rue de cette section, pas seulement
        celle-ci — n'importe quelle commune avec une section de plus de
        1000 parcelles était affectée de la même façon, silencieusement.

        Validation supplémentaire (2026-09-07, Challex, "Route de
        Pougny") : même AVEC la pagination, un appel isolé peut
        renvoyer une page tronquée de façon transitoire (35 parcelles
        renvoyées puis 135 au réessai suivant, sans aucune erreur HTTP)
        — chaque réponse APIcarto porte un champ `totalFeatures` fiable
        (confirmé en direct, présent y compris sur une page à 1 seul
        élément) ; le total accumulé est comparé à ce champ, et la
        pagination COMPLÈTE est relancée (jusqu'à 3 tentatives) en cas
        d'écart — jamais de triplement systématique du nombre de
        requêtes (coûteux sur une grosse section), seulement un nouvel
        essai quand une incohérence est réellement détectée."""
        url = f"{config.APICARTO_BASE}/cadastre/parcelle"
        for tentative in range(1, 4):
            toutes: List[dict] = []
            start = 0
            total_attendu: Optional[int] = None
            while True:
                params = {"code_insee": code_insee, "section": section, "_limit": limit, "_start": start}
                data = self._http.get_json(url, params, service_key="cadastre")
                page = data.get("features", [])
                toutes.extend(page)
                total_attendu = data.get("totalFeatures", total_attendu)
                if len(page) < limit:
                    break
                start += limit
            if total_attendu is None or len(toutes) == total_attendu:
                return toutes
            _logger.warning(
                "get_parcelles_section(%s, %s) : pagination incohérente (tentative %d/3) — "
                "%d parcelle(s) accumulée(s) vs %d annoncée(s) par l'API (totalFeatures) — "
                "nouvel essai complet.",
                code_insee, section, tentative, len(toutes), total_attendu,
            )
        _logger.error(
            "get_parcelles_section(%s, %s) : pagination toujours incohérente après 3 tentatives — "
            "renvoi du dernier résultat obtenu (%d parcelle(s)), potentiellement incomplet.",
            code_insee, section, len(toutes),
        )
        return toutes
