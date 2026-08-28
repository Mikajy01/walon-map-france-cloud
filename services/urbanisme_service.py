"""Accès aux données d'urbanisme (zonage PLU/PLUi, fiche d'information
détaillée, nature du document) via apicarto.ign.fr/api/gpu et
geoportail-urbanisme.gouv.fr/api — voir le plan."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

import config
from services.http_client import HttpClient
from utils.logger import get_logger

_logger = get_logger("services.urbanisme_service")

# Motif confirmé en investigation live pour extraire la date de révision
# d'un `idurba` (ex: "200042935_PLUi_20251014" -> "20251014") — sert au
# dédoublonnage entre versions successives d'un même document.
_RE_DATE_IDURBA = re.compile(r"_(\d{8})$")


@dataclass
class DocumentDetails:
    id: str
    type: str  # ex: "PLUi", "PLU", "POS", "CC" (carte communale), "RNU"
    title: str
    legal_status: str
    grid_rnu: Optional[bool] = None  # `grid.rnu`, confirmé présent en direct (`false` pour Arbent/PLUi)


class UrbanismeService:
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._du_categories_cache: Optional[List[Dict[str, str]]] = None
        self._sup_categories_cache: Optional[List[Dict[str, str]]] = None

    @staticmethod
    def build_parcel_id(dep: str, code_com: str, com_abs: str, prefixe: str, section: str, numero: str) -> str:
        """Construit le `parcelId` attendu par `feature-info`, format
        confirmé en investigation live :
        `{dep:2}_{code_com:3}_{com_abs:3}_{prefixe:3}_{section:2}_{numero:4}`
        (ex: `01_014_000_000_AI_0536`)."""
        return f"{dep:0>2}_{code_com:0>3}_{com_abs:0>3}_{prefixe:0>3}_{section:0>2}_{numero:0>4}"

    @staticmethod
    def code_insee_vers_parcel_id(code_insee: str, section: str, numero: str) -> str:
        """Raccourci depuis un code INSEE à 5 chiffres (dep+code_com) —
        `com_abs`/`prefixe` valent `"000"` pour toutes les communes
        rencontrées en investigation live (pas de commune associée,
        cas rare, à revoir si un jour nécessaire)."""
        dep, code_com = code_insee[:2], code_insee[2:]
        return UrbanismeService.build_parcel_id(dep, code_com, "000", "000", section, numero)

    def get_zone_urba(self, geom: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Zonage PLU/PLUi intersectant une géométrie — apicarto
        gpu/zone-urba. `geom` : géométrie GeoJSON (point ou polygone)."""
        import json
        url = f"{config.APICARTO_BASE}/gpu/zone-urba"
        params = {"geom": json.dumps(geom)}
        data = self._http.get_json(url, params, service_key="gpu")
        return data.get("features", [])

    def get_natura2000(self, geom: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Sites Natura 2000 (directives Habitats ET Oiseaux réunies)
        intersectant une géométrie — module `apicarto/nature`, DIFFÉRENT
        du module `gpu` (mais même domaine `apicarto.ign.fr`). CONFIRMÉ
        en direct : point réel dans le site "Camargue"
        (`sitecode="FR9301592"`/`"FR9310019"`) retrouvé sur les 2
        couches `natura-habitat` et `natura-oiseaux`. "Zone Nature 2000"
        (gabarit) ne distingue pas les 2 directives, donc les 2 couches
        sont interrogées et fusionnées ici."""
        import json
        params = {"geom": json.dumps(geom)}
        features: List[Dict[str, Any]] = []
        for module in ("natura-habitat", "natura-oiseaux"):
            url = f"{config.APICARTO_BASE}/nature/{module}"
            data = self._http.get_json(url, params, service_key="gpu")
            features.extend(data.get("features", []))
        return features

    def get_feature_info(
        self, category: str, type_name: Optional[str], parcel_id: str,
    ) -> List[Dict[str, Any]]:
        """`category` ∈ {du, sup, scot, mec}. `type_name` : un ou
        plusieurs `typeName` séparés par des virgules (ex:
        `"info_pct,info_lin,info_surf,prescription_pct,prescription_lin,
        prescription_surf,secteur_cc,zone_urba"`) ; `None` pour l'omettre
        entièrement — confirmé en direct nécessaire pour `category="scot"`
        (aucune liste `typeName` officielle documentée pour cette
        catégorie, contrairement à `du`/`sup` ; `typeName=""` renvoie une
        erreur 500, l'omettre renvoie les features directement, ex :
        `{"name": "scot_200040350", "title": "SCOT BUGEY", "approved":
        true}` confirmé sur une vraie parcelle d'Arboys en Bugey).

        Écart réel confirmé en direct : HTTP 404 (pas une liste vide)
        quand ce `parcelId` précis n'existe pas dans le référentiel
        cadastral de CETTE api (message explicite : "Aucune parcelle ne
        correspond à ce parcelId... Fournissez lon et lat pour interroger
        par un point.") — arrive même pour une parcelle par ailleurs
        valide côté apicarto/cadastre (référentiels non parfaitement
        synchronisés). Capturé explicitement et traité comme liste vide,
        jamais comme une erreur fatale — sans ça, une seule parcelle
        absente de ce référentiel plante tout le lot en cours."""
        url = f"{config.GPU_API_BASE}/feature-info/{category}"
        params: Dict[str, Any] = {"parcelId": parcel_id}
        if type_name is not None:
            params["typeName"] = type_name
        try:
            data = self._http.get_json(url, params, service_key="gpu")
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return []
            raise
        return data.get("features", [])

    def get_document_details(self, gpu_doc_id: str) -> DocumentDetails:
        url = f"{config.GPU_API_BASE}/document/{gpu_doc_id}/details"
        data = self._http.get_json(url, service_key="gpu")
        grid = data.get("grid") or {}
        return DocumentDetails(
            id=data["id"], type=data["type"], title=data.get("title", ""),
            legal_status=data.get("legalStatus", ""), grid_rnu=grid.get("rnu"),
        )

    def commune_a_document_du(self, code_insee: str) -> bool:
        """Existence d'AU MOINS UN document d'urbanisme LOCAL (famille
        "DU" : PLU/POS/CC/PSMV/PLUi) pour cette commune — endpoint
        `/api/document?partition=DU_<code_insee>`, CONFIRMÉ en direct
        (2026-08-25, page "Page territoire" du GPU) : liste vide pour
        Ambléon (01006, aucun document local publié, seulement des SUP)
        contre une liste réelle non vide pour Chazey-Bons (01098, PLU
        réel, `partition="DU_01098"` confirmé dans la réponse elle-même).

        Utilisé UNIQUEMENT en repli quand `resoudre_zonage` n'a trouvé
        aucun `gpu_doc_id` sur la parcelle (aucune zone `zone_urba`
        couvrante) — voir `main.py::resoudre_zonage` : "aucun document
        local" est, par construction légale (voir le plan), la
        définition même du RNU, jamais une supposition."""
        url = f"{config.GPU_API_BASE}/document"
        documents = self._http.get_json(url, {"partition": f"DU_{code_insee}"}, service_key="gpu")
        return bool(documents)

    def get_du_categories(self) -> List[Dict[str, str]]:
        """Liste officielle des 277 catégories GPU (`type`, `code`,
        `libelong`) — mise en cache en mémoire pour tout le run (appelée
        une fois par catégorie de colonne à résoudre sinon, coûteux et
        inutile puisque cette liste ne change pas en cours de run)."""
        if self._du_categories_cache is None:
            url = f"{config.GPU_API_BASE}/standard/du-categories"
            self._du_categories_cache = self._http.get_json(url, service_key="gpu")
        return self._du_categories_cache

    def get_sup_categories(self) -> List[Dict[str, str]]:
        """Liste officielle des catégories de Servitudes d'Utilité
        Publique (`name`, `libelle`, `libelleCourt`) — 66 entrées
        confirmées en investigation live, mise en cache comme
        `get_du_categories`. `name` (ex: `"EL7"`, `"PM1bis"`) est le
        code officiel retrouvé en suffixe des en-têtes du bloc SUP du
        gabarit (voir `services/excel_service.py::_extraire_code_sup`)."""
        if self._sup_categories_cache is None:
            url = f"{config.GPU_API_BASE}/standard/sup-categories"
            self._sup_categories_cache = self._http.get_json(url, service_key="gpu")
        return self._sup_categories_cache

    @staticmethod
    def dedup_par_version_recente(features: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ne garde, PAR DOCUMENT (préfixe d'`idurba` avant la date, ex
        "01017_PLUi"), que les features de la version la PLUS RÉCENTE —
        un même zonage/prescription peut apparaître pour plusieurs
        révisions successives d'un PLUi encore marquées "en production"
        simultanément, confirmé en investigation live. Les features sans
        `idurba` exploitable sont conservées telles quelles (jamais
        supprimées par prudence — un champ manquant ne doit jamais faire
        disparaître une donnée).

        Bug réel trouvé en investigation live (La Boisse, 01049, parcelle
        AI/1218, 2026-08-26) : un Plan d'Exposition au Bruit (PEB)
        d'aérodrome est structurellement INTERCOMMUNAL — publié ici sous
        `idurba="69285_PLU_20241104"` (commune du Rhône), il couvre
        géométriquement une parcelle de La Boisse dont le PLU local a
        `idurba="01049_PLU_20260309"`, une date plus récente. L'ANCIENNE
        version comparait les dates de TOUS les `idurba` entre eux sans
        regarder leur préfixe (commune + type de document), donc
        traitait à tort ce PEB comme une version PÉRIMÉE du PLU d'une
        commune totalement différente, le faisant disparaître
        silencieusement (0 "Plan d'exposition au bruit des aérodromes"
        alors que la donnée existe bel et bien). Compare désormais les
        dates SEULEMENT au sein du même préfixe — jamais entre
        documents différents."""
        avec_date = []
        sans_date = []
        for f in features:
            idurba = (f.get("properties") or {}).get("idurba", "")
            m = _RE_DATE_IDURBA.search(idurba or "")
            if m:
                prefixe = idurba[: m.start()]
                avec_date.append((prefixe, m.group(1), f))
            else:
                sans_date.append(f)
        if not avec_date:
            return features
        date_max_par_prefixe: Dict[str, str] = {}
        for prefixe, date, _ in avec_date:
            if date > date_max_par_prefixe.get(prefixe, ""):
                date_max_par_prefixe[prefixe] = date
        return [f for prefixe, date, f in avec_date if date == date_max_par_prefixe[prefixe]] + sans_date
