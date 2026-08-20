"""Extraction, comparaison et copie de la couleur de remplissage des
cellules openpyxl — utilisé pour le mécanisme de familles de couleur du
bloc de zonage (colonnes N→RR). Confirmé en investigation live : les 6
colonnes ancres (N/O/Q/R/T/Z) ont chacune une couleur de remplissage
distincte, et les 189 colonnes de code du bloc KL→RR matchent chacune
exactement l'une de ces 6 couleurs (100% de correspondance, 0 non
matchée, vérifié sur le vrai gabarit)."""

from __future__ import annotations

from typing import Optional

from openpyxl.styles import PatternFill


def rgb_de_cellule(cell) -> Optional[str]:
    """Couleur de remplissage ARGB (ex: `"FFC00000"`) d'une cellule, ou
    `None` si pas de remplissage uni. `cell` : `openpyxl.cell.cell.Cell`
    (non typé explicitement, même raison que image_hash.py)."""
    fill = cell.fill
    if fill is None or fill.patternType != "solid":
        return None
    fg = fill.fgColor
    if fg is None or not isinstance(fg.rgb, str):
        return None
    return fg.rgb


def copier_remplissage(source_rgb: str, cible) -> None:
    """Applique une couleur de remplissage unie à `cible` — utilisé lors
    de la création d'une nouvelle colonne de code, pour qu'elle porte la
    couleur de son ancre de famille (voir le plan, §"Création de
    nouvelle colonne"). Prend directement le RGB source plutôt qu'une
    cellule source, pour rester utilisable même quand la cellule ancre
    n'est plus disponible (ex: valeur mise en cache dans le registre)."""
    cible.fill = PatternFill(fill_type="solid", fgColor=source_rgb, bgColor=source_rgb)
