"""Modèle représentant UNE LIGNE DE SORTIE du fichier Excel final."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

# Sentinel utilisé comme `adresse_id` quand aucune adresse BAN n'a été
# trouvée pour une parcelle (colonne E = "/") — distinct de `None` pour
# pouvoir servir de composant de clé primaire SQLite sans ambiguïté (voir
# services/cache_service.py::ProgressStore, table `results`).
AUCUNE_ADRESSE = "__NONE__"


@dataclass
class LigneResultat:
    """Une parcelle peut produire PLUSIEURS lignes de sortie (une par
    numéro d'adresse trouvé sur son polygone, dédoublée — voir le
    plan/§Adresses) ou une seule ligne avec `adresse_id = AUCUNE_ADRESSE`
    si aucune adresse ne matche.

    `valeurs` est keyé par RÔLE DE COLONNE (`role_code`, stable), jamais
    par lettre de colonne — la traduction rôle→lettre pour un fichier
    donné se fait uniquement au moment de l'écriture, via
    `ColumnLayout.par_role` (voir models/colonne.py et
    services/excel_service.py::write_rows). Écrire directement par
    lettre romprait dès le premier fichier où une colonne a dérivé de
    position."""

    parcelle_identifiant: str
    adresse_id: str = AUCUNE_ADRESSE
    numero_adresse: str = "/"
    cote: Optional[str] = None
    ordre: Optional[float] = None
    valeurs: Dict[str, str] = field(default_factory=dict)

    @property
    def cle(self) -> tuple[str, str]:
        """Clé primaire de résumabilité — voir
        services/cache_service.py::ProgressStore, table `results`."""
        return (self.parcelle_identifiant, self.adresse_id)
