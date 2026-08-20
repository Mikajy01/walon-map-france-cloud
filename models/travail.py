"""Modèle représentant un élément de travail saisi manuellement dans le
GUI (voir le plan : pas d'import de fichier de liste, saisie directe
commune+rue avant de lancer un traitement)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ElementTravail:
    """Une ligne de la liste de travail : une rue précise d'une commune
    précise à traiter entièrement (contrairement au projet wallon, qui
    découvre lui-même toutes les rues d'une commune — voir le plan)."""

    pays: str
    commune: str
    departement: str
    rue: str
    code_postal: str
    code_insee: Optional[str] = None  # rempli par CommuneService.resolve_code_insee

    @property
    def cle(self) -> tuple[str, str, str, str]:
        """Identifiant stable de cet élément de travail, utilisé pour la
        progression au grain (commune, rue) — voir
        services/cache_service.py::ProgressStore."""
        return (self.commune, self.rue, self.departement, self.code_postal)
