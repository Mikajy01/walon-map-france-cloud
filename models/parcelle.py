"""Modèle représentant une parcelle cadastrale."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


def normaliser_numero(valeur: Any) -> str:
    """Normalise un numéro de parcelle vers sa forme canonique à 4
    chiffres (le format attendu par apicarto.ign.fr), que la valeur
    source soit un entier brut (`536`, format trouvé dans
    TRECY ARBENT.xlsx) ou une chaîne déjà préremplie de zéros (`"0050"`,
    format trouvé dans Didi-Arbent.xlsx) — écart réel constaté entre les
    deux fichiers en investigation live. Utilisé aussi bien pour
    interroger l'API cadastre que pour relire un Excel déjà rempli
    (voir services/excel_service.py::lire_identifiants_deja_ecrits)."""
    return str(int(str(valeur).strip())).zfill(4)


@dataclass
class Parcelle:
    """Une parcelle cadastrale française, identifiée par section+numéro
    au sein d'une commune (code INSEE).

    `numero` est toujours stocké sous sa forme CANONIQUE à 4 chiffres
    (`"0536"`), le format attendu par apicarto.ign.fr — même si le
    fichier Excel source/cible affiche parfois l'entier brut (`536`),
    c'est ExcelService qui fait la conversion à l'écriture/lecture,
    jamais ce modèle (voir le vrai écart constaté en investigation entre
    TRECY ARBENT.xlsx qui stocke `536` et Didi-Arbent.xlsx qui stocke
    `"0050"`).

    `geometry` est la géométrie GeoJSON (dict, EPSG:4326) renvoyée par
    apicarto.ign.fr/api/cadastre/parcelle, utilisée pour toutes les
    requêtes d'intersection spatiale (zonage, risques, adresses).
    """

    code_insee: str
    section: str
    numero: str
    commune: str
    departement: str
    code_postal: str
    rue: str
    geometry: Optional[Dict[str, Any]] = None

    # Côté ("G"/"D") et position d'ordre le long du parcours — voir
    # services/traversal_service.py. Calculés une fois, persistés pour
    # qu'une reprise après interruption ne recalcule pas le parcours.
    cote: Optional[str] = None
    ordre: Optional[float] = None

    @property
    def identifiant(self) -> str:
        """Identifiant stable utilisé pour le cache et la reprise après
        interruption — indépendant de la rue déclarée (contrairement au
        projet wallon) puisque section+numéro suffit à identifier une
        parcelle française de façon unique au sein d'une commune, sans
        dépendre d'un rattachement à une rue particulière."""
        return f"{self.code_insee}|{self.section}|{self.numero}"
