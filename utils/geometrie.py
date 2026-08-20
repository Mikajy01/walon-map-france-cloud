"""Petits calculs géométriques réutilisés par plusieurs services
(centroïde d'une géométrie GeoJSON cadastrale) — porté de la logique
ad-hoc validée en investigation live sur des géométries réelles
(Polygon/MultiPolygon à un seul anneau extérieur, jamais de trou
constaté sur une parcelle cadastrale française)."""

from __future__ import annotations

from typing import Dict, Tuple


def centroide_geometrie(geometry: Dict) -> Tuple[float, float]:
    """Centroïde approximatif (moyenne des sommets de l'anneau
    extérieur) — suffisant pour positionner une parcelle par rapport à
    une rue (pas un vrai centroïde pondéré par aire, inutile ici vu la
    taille des parcelles concernées)."""
    gtype = geometry.get("type")
    if gtype == "Polygon":
        anneau = geometry["coordinates"][0]
    elif gtype == "MultiPolygon":
        anneau = geometry["coordinates"][0][0]
    else:
        raise ValueError(f"Type de géométrie non supporté : {gtype!r}")
    lons = [c[0] for c in anneau]
    lats = [c[1] for c in anneau]
    return sum(lons) / len(lons), sum(lats) / len(lats)
