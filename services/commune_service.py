"""Résolution nom de commune -> code INSEE — sans équivalent côté
wallon (le projet wallon travaille directement avec un registre de
géocodage belge qui n'a pas ce besoin). Chaque appel aux 4 familles
d'APIs françaises utilisées dans ce projet a besoin du code INSEE, donc
cette résolution est la toute première étape de tout traitement.

Confirmé en investigation live : `geo.api.gouv.fr/communes` répond
correctement et gratuitement, sans clé — voir le plan."""

from __future__ import annotations

from typing import List

import config
from services.exceptions import ApiServiceError
from services.http_client import HttpClient
from utils.logger import get_logger

_logger = get_logger("services.commune_service")


class CommuneService:
    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def resolve_code_insee(self, commune: str, departement: str, code_postal: str) -> str:
        """Résout le code INSEE d'une commune, désambiguïsé par
        département ET code postal (plusieurs communes françaises
        partagent le même nom dans des départements différents — ne
        jamais deviner, lever une erreur explicite si le résultat n'est
        pas unique après filtrage plutôt que de prendre le premier venu)."""
        url = f"{config.COMMUNE_API_BASE}/communes"
        params = {
            "nom": commune,
            "fields": "nom,code,codesPostaux,departement",
            "format": "json",
        }
        data = self._http.get_json(url, params, service_key="commune")
        if not isinstance(data, list):
            raise ApiServiceError(f"Réponse inattendue de {url} pour commune={commune!r}: {data!r}")

        dep_norm = departement.strip().lstrip("0") or "0"
        dep_nom_norm = departement.strip().lower()
        cp_norm = code_postal.strip()
        if cp_norm.isdigit():
            # Un code postal français fait TOUJOURS 5 chiffres (zéro
            # initial pour les départements 01-09) — écart réel trouvé
            # en investigation live (2026-08-19) : une saisie GUI sans
            # le zéro initial ("1300" au lieu de "01300") échouait la
            # comparaison exacte avec `codesPostaux`, produisant "Aucune
            # commune trouvée" alors que la commune existe bel et bien.
            cp_norm = cp_norm.zfill(5)
        candidats: List[dict] = [
            c for c in data
            if cp_norm in (c.get("codesPostaux") or [])
            and (
                # Accepte le CODE ("01") OU le NOM ("Ain") du département
                # — écart réel trouvé en direct via un screenshot GUI
                # (2026-08-19) : l'utilisateur a naturellement tapé "Ain"
                # dans le champ Département (ce qu'il connaît vraiment),
                # pas le code numérique "01", et ça échouait silencieusement
                # sur "Aucune commune trouvée" alors que le nom et le code
                # postal étaient corrects tous les deux.
                str(c.get("departement", {}).get("code", "")).strip().lstrip("0") == dep_norm
                or str(c.get("departement", {}).get("nom", "")).strip().lower() == dep_nom_norm
            )
        ]

        if not candidats:
            raise ApiServiceError(
                f"Aucune commune trouvée pour nom={commune!r} departement={departement!r} "
                f"code_postal={code_postal!r} (candidats bruts: {data!r})"
            )
        if len(candidats) > 1:
            raise ApiServiceError(
                f"Résolution ambiguë pour nom={commune!r} departement={departement!r} "
                f"code_postal={code_postal!r} : {len(candidats)} candidats {candidats!r}"
            )
        code_insee = candidats[0]["code"]
        _logger.info("Commune '%s' (%s, %s) -> code_insee=%s", commune, departement, code_postal, code_insee)
        return code_insee

    def lister_voies(self, code_insee: str) -> List[str]:
        """Découverte automatique de TOUTES les voies d'une commune —
        besoin propre au contexte cloud (voir le plan, 2026-08-20) :
        contrairement au desktop, où l'utilisateur tape les rues à la
        main, le workflow GitHub Actions traite une commune entière.

        Vérifié en direct pendant la planification, pas deviné :
        `plateforme.adresse.data.gouv.fr/lookup/{code_insee}` renvoie un
        objet commune avec `voies[].nomVoie` — testé sur 01015 (Arboys
        en Bugey) : 85 voies renvoyées, tableau complet (pas de
        pagination — `len(voies)` dépasse même le `nbVoies` annoncé),
        contient bien "Montée du Mollard" et "Montée de la Quoille",
        deux rues réelles déjà traitées dans ce projet."""
        url = f"{config.ADRESSE_PLATEFORME_BASE}/lookup/{code_insee}"
        data = self._http.get_json(url, service_key="commune")
        if not isinstance(data, dict) or "voies" not in data:
            raise ApiServiceError(f"Réponse inattendue de {url} pour code_insee={code_insee!r}: {data!r}")

        noms = sorted({v["nomVoie"] for v in data["voies"] if v.get("nomVoie")})
        _logger.info("Commune %s : %d voie(s) découverte(s).", code_insee, len(noms))
        return noms
