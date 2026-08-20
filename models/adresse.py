"""Modèle représentant un point d'adresse BAN (Base Adresse Nationale)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AdressePoint:
    """Un point d'adresse réel renvoyé par le géocodage inverse IGN
    (data.geopf.fr/geocodage/reverse).

    `id` est l'identifiant BAN, au format confirmé en investigation live
    `{code_insee}_{voie_id}_{numero}` (ex: `"01014_0165_00006"`) — le
    `voie_id` (`"0165"`) est un identifiant de tronçon de rue stable,
    plus fiable que le nom de rue en texte libre pour regrouper les
    adresses d'une même rue (voir `.voie_id` ci-dessous et
    services/traversal_service.py, qui reconstruit une polyligne à
    partir de ce regroupement plutôt que par nom de rue)."""

    id: str
    housenumber: str
    street: str
    lon: float
    lat: float

    @property
    def voie_id(self) -> str:
        """Segment stable de l'`id` BAN identifiant le tronçon de rue.

        Renvoie une chaîne vide si `id` ne suit pas le format attendu
        (3 segments séparés par `_`) plutôt que de lever une exception —
        un identifiant BAN inattendu ne doit jamais faire échouer tout
        le traitement, seulement dégrader le regroupement par tronçon."""
        parts = self.id.split("_")
        return parts[1] if len(parts) >= 3 else ""

    @property
    def numero_parite(self) -> str:
        """"pair"/"impair", utilisé comme signal primaire de côté de rue
        (convention française : numéros pairs/impairs sur des côtés
        opposés) — voir services/traversal_service.py."""
        chiffres = "".join(c for c in self.housenumber if c.isdigit())
        if not chiffres:
            return "impair"
        return "pair" if int(chiffres) % 2 == 0 else "impair"
