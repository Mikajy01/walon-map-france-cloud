"""Extraction et hachage des icônes intégrées dans les cellules d'un
classeur Excel (bloc H→HV du gabarit français) — voir le plan : l'icône
reste identique d'un fichier à l'autre même quand le texte de l'en-tête
dérive/est tronqué, confirmé par hash MD5 en investigation live sur les
2 vrais exemplaires (TRECY ARBENT.xlsx / Didi-Arbent.xlsx)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class IconeCellule:
    column_index: int  # 1-based, convention openpyxl pour les colonnes de cellules
    png_bytes: bytes
    hash_md5: str


def hash_icone(png_bytes: bytes) -> str:
    """Hash MD5 des octets bruts du PNG. Confirmé en investigation live :
    stable entre deux fichiers réels pour la même icône logique, y
    compris quand le texte de la colonne associée diffère (cas réel :
    "Zone Humide / Espaces remarquables du littoral" vs "Espaces
    remarquables du littoral", icônes identiques)."""
    return hashlib.md5(png_bytes).hexdigest()


def extraire_icones_par_colonne(ws, icon_row_index: int = 0) -> Dict[int, List[IconeCellule]]:
    """Extrait, pour chaque colonne ayant au moins une icône ancrée à la
    ligne `icon_row_index` (0-indexée, convention openpyxl — confirmé en
    investigation live que les icônes du bloc H→HV sont ancrées à la
    ligne 1 du classeur = index 0, une ligne au-dessus de la ligne
    d'en-tête texte qui elle est en ligne 2), TOUTES ses icônes (liste,
    jamais une seule).

    `ws` : `openpyxl.worksheet.worksheet.Worksheet` (non typé
    explicitement pour éviter une dépendance d'import lourde ici).

    Plusieurs images peuvent être ancrées sur la même colonne (observé
    dans TRECY ARBENT.xlsx, colonne AD ; puis réellement exploité dans
    "Tableau Geoportail France Off 4.xlsx", 2026-08-25, colonnes CF/FW —
    une administration y a AJOUTÉ une 2e icône à une cellule qui en avait
    déjà une). Renvoyées dans l'ordre de `ws._images` (reflète l'ordre du
    XML source) — observé en direct sur ces 2 cas réels : une icône
    AJOUTÉE arrive toujours APRÈS l'icône déjà présente, jamais avant,
    donc le PREMIER élément de la liste est toujours l'icône d'origine/
    "propriétaire" de la colonne (voir `services/excel_service.py::
    bootstrap_from_template`, qui s'appuie sur cet ordre pour ne jamais
    laisser un ajout thématique redéfinir l'identité déjà établie
    d'une colonne, ni écraser l'identité globale d'une icône empruntée
    à une AUTRE colonne)."""
    resultat: Dict[int, List[IconeCellule]] = {}
    # `ws._images` est une API privée d'openpyxl, mais c'est la seule
    # voie disponible pour lire les images déjà présentes dans un
    # classeur chargé (par opposition à `ws.add_image`, qui n'aide qu'à
    # en AJOUTER une).
    for image in ws._images:
        anchor_row = image.anchor._from.row
        if anchor_row != icon_row_index:
            continue
        col_index = image.anchor._from.col + 1
        png_bytes = image._data()
        resultat.setdefault(col_index, []).append(
            IconeCellule(column_index=col_index, png_bytes=png_bytes, hash_md5=hash_icone(png_bytes)),
        )
    return resultat
