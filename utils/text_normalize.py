"""Normalisation de texte et correspondance floue — utilisées en DERNIER
recours par column_registry_service (suggestion seulement, jamais
appliquée automatiquement, voir le plan)."""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Tuple

from rapidfuzz import fuzz


def normaliser(texte: Optional[str]) -> str:
    """Normalise un TEXTE LIBRE (en-tête de colonne, alias) pour
    comparaison : supprime les accents, passe en minuscules, réduit tout
    séparateur (espaces, espaces insécables, ponctuation) à un simple
    espace. Utilisé pour les en-têtes/alias, où la casse n'a jamais de
    sens métier (une même colonne peut légitimement varier en casse
    d'un fichier à l'autre sans changer de nature).

    JAMAIS utilisé pour un CODE DE ZONE — voir `normaliser_code_zone`,
    où au contraire la casse EST significative (décision explicite de
    l'utilisateur, 2026-08-21 : "Ua" et "UA" sont des zones réellement
    différentes, jamais fusionnées)."""
    if not texte:
        return ""
    t = unicodedata.normalize("NFKD", texte)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return t.strip()


def normaliser_code_zone(code: Optional[str]) -> str:
    """Normalise un CODE DE ZONE (PLU/PLUi, ex "1AUd", "Ua3", "UXa") pour
    comparaison/stockage — CONTRAIREMENT à `normaliser()` (texte libre),
    la CASSE EST SIGNIFICATIVE ici et n'est JAMAIS modifiée : décision
    explicite de l'utilisateur (2026-08-21) — "Ua" et "UA" désignent des
    zones réellement différentes dans la pratique observée, jamais la
    même colonne, même si le principe général de ce projet privilégie
    l'insensibilité à la casse pour le texte libre. Seuls les accents et
    les espaces parasites (espaces insécables notamment, même écart réel
    déjà rencontré sur les noms de rue) sont retirés — jamais la casse,
    jamais les caractères eux-mêmes."""
    if not code:
        return ""
    t = unicodedata.normalize("NFKD", code)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\s+", "", t)
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
