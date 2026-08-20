"""Normalisation de texte et correspondance floue — utilisées en DERNIER
recours par column_registry_service (suggestion seulement, jamais
appliquée automatiquement, voir le plan)."""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Tuple

from rapidfuzz import fuzz


def normaliser(texte: Optional[str]) -> str:
    """Normalise un texte pour comparaison : supprime les accents, passe
    en minuscules, réduit tout séparateur (espaces, espaces insécables,
    ponctuation) à un simple espace. Confirmé nécessaire en
    investigation live : casse différente d'un même code entre deux
    fichiers réels (`"UA3"` vs `"Ua3"`, `"Uxa"` vs `"UXa"`), espaces
    insécables (`\\xa0`) en fin de plusieurs noms de rue."""
    if not texte:
        return ""
    t = unicodedata.normalize("NFKD", texte)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def meilleure_correspondance(
    texte: str, candidats: List[Tuple[str, str]]
) -> Optional[Tuple[str, str, float]]:
    """`candidats` : liste de `(role_code, libelle_canonique)`. Renvoie
    `(role_code, libelle, score 0..1)` du meilleur candidat, ou `None` si
    `candidats` est vide.

    Ne décide JAMAIS d'un seuil d'acceptation — c'est
    `ColumnRegistryService` qui applique le seuil et journalise la
    suggestion ; cette fonction reste un pur outil de scoring, réutilisable
    tel quel pour n'importe quel bloc de colonnes (Géorisques, GPU...)."""
    if not candidats:
        return None
    texte_norm = normaliser(texte)
    meilleur: Optional[Tuple[str, str, float]] = None
    meilleur_score = -1.0
    for role_code, libelle in candidats:
        score = fuzz.ratio(texte_norm, normaliser(libelle)) / 100.0
        if score > meilleur_score:
            meilleur_score = score
            meilleur = (role_code, libelle, score)
    return meilleur
