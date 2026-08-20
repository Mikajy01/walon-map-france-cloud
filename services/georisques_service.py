"""Accès aux données de risques naturels/technologiques via
georisques.gouv.fr/api/v1 — voir le plan.

Chaque méthode est un adaptateur DÉDIÉ à un endpoint, jamais un appelant
générique : confirmé en investigation live que les noms de paramètres
sont incohérents d'un endpoint à l'autre (la plupart en snake_case
`code_insee`, mais `gaspar/pprn` utilise `codeInsee` en camelCase, et
`installations_nucleaires` utilise `longitude`/`latitude` séparés plutôt
que `latlon`)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

import config
from services.http_client import HttpClient
from utils.logger import get_logger

_logger = get_logger("services.georisques_service")


class GeorisquesService:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def _url(self, cle_endpoint: str) -> str:
        return config.GEORISQUES_API_BASE + config.GEORISQUES_ENDPOINTS[cle_endpoint]

    # -- confirmés exacts en investigation live --------------------

    def get_rga(self, lat: float, lon: float, rayon: int = 200) -> Optional[Dict[str, Any]]:
        """Exposition au retrait-gonflement des argiles — colonnes
        "Argiles Exposition Moyen/Faible/Forte". Confirmé exact contre
        données réelles ("Exposition moyenne"/"faible")."""
        data = self._http.get_json(
            self._url("rga"), {"latlon": f"{lon},{lat}", "rayon": rayon}, service_key="georisques",
        )
        return data if data else None

    def get_radon(self, code_insee: str) -> Optional[Dict[str, Any]]:
        """Catégorie de potentiel radon (niveau commune) — colonnes
        "Catégorie 1/2/3". Confirmé exact (`classe_potentiel`)."""
        data = self._http.get_json(self._url("radon"), {"code_insee": code_insee}, service_key="georisques")
        results = data.get("data", [])
        return results[0] if results else None

    def get_zonage_sismique(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Zone de sismicité (niveau commune) — colonnes "Sismicité très
        faible/faible/modérée/moyenne/forte". Confirmé exact
        (`zone_sismicite`, ex: "3 - MODEREE")."""
        data = self._http.get_json(
            self._url("zonage_sismique"), {"latlon": f"{lon},{lat}"}, service_key="georisques",
        )
        results = data.get("data", [])
        return results[0] if results else None

    def get_casias(self, lat: float, lon: float, rayon: int = 500) -> List[Dict[str, Any]]:
        """Anciens sites industriels et activités de service — colonne
        "Anciens sites industriels et activités de service". Confirmé :
        site réel retrouvé sur la bonne rue en investigation live."""
        data = self._http.get_json(
            self._url("casias"), {"latlon": f"{lon},{lat}", "rayon": rayon}, service_key="georisques",
        )
        return data.get("data", [])

    # -- endpoints à paramètres non standard -----------------------

    def get_installations_nucleaires(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        """Installations nucléaires "à proximité selon le plan
        particulier d'intervention" — PAS de `rayon`/`latlon`, paramètres
        `longitude`/`latitude` séparés (confirmé : HTTP 500 sinon)."""
        data = self._http.get_json(
            self._url("installations_nucleaires"), {"longitude": lon, "latitude": lat},
            service_key="georisques",
        )
        return data if isinstance(data, list) else []

    def get_gaspar_pprn(
        self, code_insee: Optional[str] = None, lon: Optional[float] = None, lat: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """PPR naturels (inondation, mouvement de terrain, etc.) — soit
        pour une commune entière (`code_insee`, paramètre `codeInsee` en
        camelCase, confirmé : avec `code_insee` en snake_case, le filtre
        est ignoré et l'API renvoie le jeu de données NATIONAL entier,
        ~6500 éléments), soit pour un POINT précis (`lon`/`lat`) —
        confirmé en direct que ce dernier fait une vraie intersection
        géométrique (testé sur Lyon : un point au centre-ville/bord du
        Rhône trouve le PPRI actif, un point à ~5km en trouve zéro),
        utilisable au niveau parcelle (colonnes "PPR <risque>" sans
        "sur la commune")."""
        params: Dict[str, Any] = {}
        if code_insee is not None:
            params["codeInsee"] = code_insee
        if lon is not None and lat is not None:
            params["longitude"] = lon
            params["latitude"] = lat
        data = self._http.get_json(self._url("gaspar_pprn"), params, service_key="georisques")
        return data.get("content", [])

    def get_gaspar_pprt(
        self, code_insee: Optional[str] = None, lon: Optional[float] = None, lat: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """PPR technologiques — même remarque `codeInsee`/`lon`+`lat` que `pprn`."""
        params: Dict[str, Any] = {}
        if code_insee is not None:
            params["codeInsee"] = code_insee
        if lon is not None and lat is not None:
            params["longitude"] = lon
            params["latitude"] = lat
        data = self._http.get_json(self._url("gaspar_pprt"), params, service_key="georisques")
        return data.get("content", [])

    def get_gaspar_pprm(
        self, code_insee: Optional[str] = None, lon: Optional[float] = None, lat: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """PPR miniers — même remarque `codeInsee`/`lon`+`lat` que `pprn`."""
        params: Dict[str, Any] = {}
        if code_insee is not None:
            params["codeInsee"] = code_insee
        if lon is not None and lat is not None:
            params["longitude"] = lon
            params["latitude"] = lat
        data = self._http.get_json(self._url("gaspar_pprm"), params, service_key="georisques")
        return data.get("content", [])

    # -- structurels/génériques -------------------------------------

    def get_cavites(self, code_insee: str) -> List[Dict[str, Any]]:
        data = self._http.get_json(self._url("cavites"), {"code_insee": code_insee}, service_key="georisques")
        return data.get("data", [])

    def get_mvt(self, lat: float, lon: float, rayon: int = 1000) -> List[Dict[str, Any]]:
        """Mouvements de terrain répertoriés."""
        data = self._http.get_json(
            self._url("mvt"), {"latlon": f"{lon},{lat}", "rayon": rayon}, service_key="georisques",
        )
        return data.get("data", [])

    def get_mvt_commune(self, code_insee: str) -> List[Dict[str, Any]]:
        """Mouvements de terrain d'une commune entière (paramètre
        `code_insee`, confirmé en direct incompatible avec `rayon` —
        colonne "Mouvements de terrain non localisés" : `precision_lieu`
        (valeurs réelles observées : "Mètre", "Décamètre", "Hectomètre",
        "Commune") vaut "Commune" pour un enregistrement dont la
        localisation précise est inconnue — c'est le signal utilisé,
        voir `services/georisques_rules.py::_existence_mvt_non_localise`."""
        data = self._http.get_json(self._url("mvt"), {"code_insee": code_insee}, service_key="georisques")
        return data.get("data", [])

    def get_old(self, code_insee: Optional[str] = None, lat: Optional[float] = None, lon: Optional[float] = None) -> List[Dict[str, Any]]:
        """Obligation légale de débroussaillement (OLD) — colonne
        "(Zonage informatif des obligations légales de debroussaillement".
        CONFIRMÉ en direct (Toulon, 83137) : renvoie une vraie liste avec
        `commune`/`coordonnees`/`risque` (dont l'URL de l'arrêté
        préfectoral). Écart réel confirmé : HTTP 404 "Pas de résultat
        trouvé" (pas une liste vide) quand aucune obligation ne
        s'applique (confirmé sur Arbent) — capturé explicitement et
        traité comme liste vide, jamais comme une erreur transitoire."""
        params: Dict[str, Any] = {}
        if code_insee is not None:
            params["code_insee"] = code_insee
        if lat is not None and lon is not None:
            params["latlon"] = f"{lon},{lat}"
        try:
            data = self._http.get_json(self._url("old"), params, service_key="georisques")
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return []
            raise
        return data if isinstance(data, list) else []

    def get_gaspar_azi(self, code_insee: str) -> List[Dict[str, Any]]:
        """Zones inondables répertoriées (Atlas des Zones Inondables)."""
        data = self._http.get_json(
            self._url("gaspar_azi"), {"code_insee": code_insee}, service_key="georisques",
        )
        return data.get("data", [])

    @staticmethod
    def sup_existe(ppr_record: Dict[str, Any]) -> bool:
        """Extrait le champ `supExists` d'un enregistrement PPR
        (`get_gaspar_pprn`/`pprt`/`pprm`) — alimente directement le
        sous-bloc "SUP <risque>" (colonnes JP→JV) sans endpoint séparé,
        confirmé présent dans chaque enregistrement PPR réel."""
        return bool(ppr_record.get("supExists"))

    def get_gaspar_tim(self, code_insee: str) -> List[Dict[str, Any]]:
        """Transport de matières dangereuses (canalisations) — confirmé
        en direct : renvoie un vrai enregistrement pour Arbent."""
        data = self._http.get_json(self._url("gaspar_tim"), {"code_insee": code_insee}, service_key="georisques")
        return data.get("data", [])

    def get_resultats_rapport_risque(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """Rapport de synthèse par adresse/point — confirmé en direct :
        `risquesNaturels.remonteeNappe.present` retrouvé correctement
        pour un point réel d'Arbent. Contient aussi inondation, séisme,
        mouvementsTerrain, risquesTechnologiques, etc. (voir la clé
        `risquesNaturels`/`risquesTechnologiques` de la réponse)."""
        data = self._http.get_json(
            self._url("resultats_rapport_risque"), {"latlon": f"{lon},{lat}"}, service_key="georisques",
        )
        return data if data else None

    def get_ssp(self, code_insee: str) -> List[Dict[str, Any]]:
        """Secteurs d'Information sur les Sols (SSP), jeu de base —
        candidat structurel pour "Sites pollués ... BASOL", jamais
        confirmé contre un exemple réel positif (0 résultat pour
        Arbent, aucune commune testée n'en a)."""
        data = self._http.get_json(self._url("ssp"), {"code_insee": code_insee}, service_key="georisques")
        return data.get("data", [])

    def get_ssp_conclusions_sis(self, code_insee: str) -> List[Dict[str, Any]]:
        """Secteur d'Information sur les Sols (SIS) — candidat
        structurel, jamais confirmé (même remarque que `get_ssp`)."""
        data = self._http.get_json(
            self._url("ssp_conclusions_sis"), {"code_insee": code_insee}, service_key="georisques",
        )
        return data.get("data", [])

    def get_ssp_conclusions_sup(self, code_insee: str) -> List[Dict[str, Any]]:
        """Servitude d'Utilité Publique liée aux sols pollués — candidat
        structurel, jamais confirmé (même remarque que `get_ssp`)."""
        data = self._http.get_json(
            self._url("ssp_conclusions_sup"), {"code_insee": code_insee}, service_key="georisques",
        )
        return data.get("data", [])
