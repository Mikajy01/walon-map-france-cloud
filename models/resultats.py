"""Dataclasses de résultat renvoyées par les fonctions d'orchestration de
main.py — même motif que project/main.py (petites dataclasses avec une
propriété `.termine`, lues aussi bien par le CLI que par gui.py)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ResultatRue:
    """Résultat du traitement d'UN `ElementTravail` (une rue précise
    d'une commune) — équivalent du `ResultatTraitement` wallon, mais au
    grain rue plutôt que commune (voir le plan)."""

    commune: str
    rue: str
    lignes_ecrites: int = 0
    parcelles_traitees: int = 0
    echecs: int = 0
    colonnes_non_resolues: List[str] = field(default_factory=list)
    nouvelles_colonnes: List[str] = field(default_factory=list)
    # Deux cas bien distincts (décision explicite de l'utilisateur,
    # 2026-08-21 — remplace l'ancien repli uniforme à "N" du 2026-08-18,
    # trompeur car indiscernable d'une vraie réponse négative), tous deux
    # journalisés dans un fichier de suivi pour revisite (voir main.py::
    # _forcer_valeurs_manquantes_en_n) :
    #
    # Rôle connu de ce fichier mais SANS AUCUNE règle de calcul possible
    # (voir config.ROLES_SANS_REGLE + tout rôle `icone::*`) — écrit
    # "Manuellement", jamais récupérable par le bouton "Retraiter les
    # erreurs" tant qu'aucune règle n'est construite.
    cellules_manuelles: int = 0
    # Rôle connu de ce fichier AVEC une règle implémentée, mais qui n'a
    # produit aucune valeur pour cette parcelle précise (échec réseau/API
    # ponctuel) — écrit "ERREUR", récupérable via le bouton "Retraiter
    # les erreurs" (voir main.py::reessayer_cellules_wfs/
    # reessayer_cellules_gpu_du).
    cellules_erreur: int = 0
    # True si le traitement de cette rue a été interrompu par le budget
    # de temps (limite 6h de GitHub Actions, voir le plan cloud
    # 2026-08-20), pas par manque de parcelles à traiter — signal pour
    # `traiter_commune_complete` qu'une reprise sera nécessaire au run
    # suivant. N'affecte jamais l'intégrité des données déjà écrites :
    # `traiter_rue` ne s'arrête qu'ENTRE deux parcelles, jamais en cours
    # de calcul d'une parcelle.
    arrete_par_budget: bool = False

    @property
    def termine(self) -> bool:
        """False si des échecs ou des colonnes non résolues subsistent
        — signal à l'appelant (CLI/GUI) qu'un retraitement ou une revue
        du registre de colonnes est nécessaire avant de considérer cette
        rue comme réellement finie."""
        return self.echecs == 0 and not self.colonnes_non_resolues


@dataclass
class ResultatLot:
    """Résultat agrégé du traitement d'un lot d'`ElementTravail` (une
    session GUI, ou un batch CLI) — construit en accumulant des
    `ResultatRue`, jamais recalculé indépendamment."""

    resultats_par_rue: List[ResultatRue] = field(default_factory=list)
    colonnes_creees: List[str] = field(default_factory=list)
    # True si `traiter_commune_complete` a dû s'arrêter avant la fin de
    # la commune (budget de temps atteint, voir `ResultatRue.
    # arrete_par_budget`) OU avant même d'avoir pu traiter toutes les
    # rues découvertes — signal explicite pour le workflow GitHub
    # Actions ("reprise nécessaire au run suivant, relancer en
    # 'continuer'"), jamais silencieux.
    incomplet: bool = False
    rues_restantes: List[str] = field(default_factory=list)

    @property
    def total_lignes_ecrites(self) -> int:
        return sum(r.lignes_ecrites for r in self.resultats_par_rue)

    @property
    def total_echecs(self) -> int:
        return sum(r.echecs for r in self.resultats_par_rue)

    @property
    def total_cellules_manuelles(self) -> int:
        return sum(r.cellules_manuelles for r in self.resultats_par_rue)

    @property
    def total_cellules_erreur(self) -> int:
        return sum(r.cellules_erreur for r in self.resultats_par_rue)

    @property
    def termine(self) -> bool:
        return all(r.termine for r in self.resultats_par_rue)

    def resume(self) -> str:
        """Résumé humain multi-lignes, affiché en fin de run (CLI et
        GUI) — même rôle que `RapportRecalcul.resume` côté wallon."""
        lignes = [
            f"{len(self.resultats_par_rue)} rue(s) traitée(s), "
            f"{self.total_lignes_ecrites} ligne(s) écrite(s), "
            f"{self.total_echecs} échec(s).",
        ]
        if self.colonnes_creees:
            lignes.append(
                f"{len(self.colonnes_creees)} nouvelle(s) colonne(s) créée(s) : "
                + ", ".join(self.colonnes_creees)
                + " — à relayer manuellement (Teams)."
            )
        non_resolues = {c for r in self.resultats_par_rue for c in r.colonnes_non_resolues}
        if non_resolues:
            lignes.append(
                f"{len(non_resolues)} colonne(s) non résolue(s), laissées vides : "
                + ", ".join(sorted(non_resolues))
                + " — à classer dans le registre de colonnes."
            )
        if self.total_cellules_erreur:
            lignes.append(
                f"{self.total_cellules_erreur} cellule(s) en \"ERREUR\" (règle existante, échec "
                "ponctuel) — récupérables via le bouton \"Retraiter les erreurs\"."
            )
        if self.total_cellules_manuelles:
            lignes.append(
                f"{self.total_cellules_manuelles} cellule(s) marquée(s) \"Manuellement\" (aucune "
                "règle de calcul possible) — à remplir à la main, jamais récupérables automatiquement."
            )
        if self.incomplet:
            lignes.append(
                f"INCOMPLET : budget de temps atteint avant la fin de la commune, "
                f"{len(self.rues_restantes)} rue(s) encore non traitée(s) : "
                + ", ".join(self.rues_restantes)
                + " — relancer le workflow en mode 'continuer' pour reprendre."
            )
        return "\n".join(lignes)
