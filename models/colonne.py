"""Modèles pour la résolution d'identité de colonne — le cœur du projet,
sans équivalent côté wallon (voir le plan : `COLUMN_RULES` là-bas suppose
des lettres de colonne fixes, ce qui n'est pas vrai ici puisque les
en-têtes dérivent d'un fichier à l'autre).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class MethodeResolution(str, Enum):
    """Comment le rôle d'une colonne a été déterminé — voir
    services/column_registry_service.py::resolve_column pour l'ordre
    exact des couches essayées. Seules ICONE/CODE/ALIAS/CREEE comptent
    comme "résolu" pour l'écriture de données ; SUGGESTION_FLOUE et
    NON_RESOLU laissent la colonne vide ce run."""

    ICONE = "icone"
    CODE = "code"
    ALIAS = "alias"
    CREEE = "creee"
    SUGGESTION_FLOUE = "suggestion_floue"
    NON_RESOLU = "non_resolu"


@dataclass(frozen=True)
class ColumnResolution:
    """Résultat de la résolution d'UNE colonne d'un fichier donné."""

    column_letter: str
    header_text: str
    role_code: Optional[str]
    method: MethodeResolution
    confidence: float
    icon_hash: Optional[str] = None
    normalized_code: Optional[str] = None

    @property
    def resolu(self) -> bool:
        """True si la colonne peut être utilisée pour écrire des données
        ce run — False pour SUGGESTION_FLOUE/NON_RESOLU, qui ne doivent
        jamais recevoir de valeur devinée silencieusement."""
        return self.method not in (
            MethodeResolution.SUGGESTION_FLOUE,
            MethodeResolution.NON_RESOLU,
        )


@dataclass(frozen=True)
class ColonneCreeeEvent:
    """Une colonne insérée par la Phase A (voir `services/excel_service.
    py::ensure_columns_for_codes`). Canal VOLONTAIREMENT séparé du
    logger général : décision utilisateur explicite — cette information
    sert de base au relais manuel Teams, elle ne doit jamais être noyée
    dans le flux de log courant (main.py/gui.py la routent chacun vers
    un canal dédié, pas vers le Journal)."""

    column_letter: str
    code: str
    color_family_id: str
    lettre_avant: str
    entete_avant: str
    lettre_apres: str
    entete_apres: str


@dataclass
class ColumnLayout:
    """Disposition figée des colonnes d'UN fichier de sortie pour UN run.

    Construite une seule fois par `ExcelService.scan_layout` (complétée
    par `ensure_columns_for_codes` lors de la "Phase A" de création de
    colonnes, voir le plan), puis utilisée en lecture seule pendant toute
    la Phase B (remplissage des données) — aucune modification de
    structure ne doit survenir après que `par_role` a été construit,
    sous peine de décaler les lettres déjà résolues."""

    resolutions: List[ColumnResolution] = field(default_factory=list)

    @property
    def par_role(self) -> Dict[str, List[str]]:
        """{role_code: [column_letter, ...]} pour toutes les colonnes
        résolues — reconstruit à la volée depuis `resolutions` plutôt que
        maintenu séparément, pour ne jamais risquer une désynchronisation
        entre les deux.

        Valeur en LISTE, pas une seule lettre : écart réel trouvé en
        investigation live (Arboys en Bugey) — deux colonnes bien
        DIFFÉRENTES du même fichier peuvent légitimement résoudre vers le
        même `role_code` (ex : plusieurs icônes distinctes mappées au même
        code SUP officiel, ex "AS1" pour "protection immédiate/rapprochée/
        éloignée/eau minérale" — 4 colonnes réelles, 1 seul code SUP
        commun). Une valeur à lettre UNIQUE ferait perdre silencieusement
        toutes les colonnes sauf la dernière rencontrée (23 cas réels
        trouvés sur un seul fichier traité), ces colonnes restant alors
        vides à vie sans qu'aucun signal n'indique pourquoi."""
        par_role: Dict[str, List[str]] = {}
        for r in self.resolutions:
            if r.resolu and r.role_code:
                par_role.setdefault(r.role_code, []).append(r.column_letter)
        return par_role

    def lettre_pour_role(self, role_code: str) -> Optional[str]:
        """Une seule lettre (la première rencontrée) — pour les usages
        qui ne veulent savoir QUE si un rôle a une colonne dans ce
        fichier (ex : Phase A), jamais pour ÉCRIRE une valeur (voir
        `lettres_pour_role`, utilisé par `write_ligne` pour écrire dans
        TOUTES les colonnes partageant ce rôle, pas seulement la
        première)."""
        lettres = self.par_role.get(role_code)
        return lettres[0] if lettres else None

    def lettres_pour_role(self, role_code: str) -> List[str]:
        return self.par_role.get(role_code, [])

    def non_resolues(self) -> List[ColumnResolution]:
        return [r for r in self.resolutions if not r.resolu]
