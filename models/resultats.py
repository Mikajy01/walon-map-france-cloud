"""Dataclasses de résultat renvoyées par les fonctions d'orchestration de
main.py — même motif que project/main.py (petites dataclasses avec une
propriété `.termine`, lues aussi bien par le CLI que par gui.py)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from models.colonne import ColonneCreeeEvent


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
    # Détail complet (position + voisins) de chaque colonne créée durant
    # ce run — décision explicite de l'utilisateur (2026-08-21) : le
    # résumé final (log, GitHub Actions comme desktop) doit lister CHAQUE
    # colonne avec sa place exacte, pas seulement son code, pour que le
    # relais manuel (Teams) n'ait pas besoin d'aller rouvrir le fichier.
    # Même évènement que celui déjà notifié en direct au moment de la
    # création (voir main.py::_notifier_colonne_creee_cli) — accumulé
    # ici en plus, jamais à la place.
    colonnes_creees_detail: List[ColonneCreeeEvent] = field(default_factory=list)
    # Compte GLOBAL des cellules "ERREUR"/"Manuellement" actuellement
    # dans le fichier, lu directement (voir main.py::
    # compter_cellules_forcees_fichier), PAS seulement celles produites
    # par ce run précis — décision explicite de l'utilisateur
    # (2026-08-21) : le résumé final doit donner une vision d'ensemble du
    # travail restant, peu importe depuis combien de runs une cellule
    # traîne. `None` (défaut) = non renseigné par l'appelant, `resume()`
    # retombe alors sur les compteurs par-run (`total_cellules_erreur`/
    # `total_cellules_manuelles`) pour rester rétrocompatible.
    cellules_erreur_fichier: Optional[int] = None
    cellules_manuelles_fichier: Optional[int] = None
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
        # Depuis 2026-08-24 (décision utilisateur : "il ne faut plus faire
        # d'insertion de colonne"), `ensure_columns_for_codes` n'insère
        # plus jamais rien — ces évènements signalent seulement un code de
        # zone absent, `column_letter`/`lettre_avant`/`entete_avant`/
        # `lettre_apres`/`entete_apres` sont désormais TOUJOURS vides (plus
        # de position à afficher). Le texte disait encore "créée(s)"
        # jusqu'ici, ce qui laissait croire qu'une colonne avait été
        # insérée alors qu'aucune ne l'est plus — corrigé ici.
        if self.colonnes_creees_detail:
            lignes.append(
                f"{len(self.colonnes_creees_detail)} code(s) de zone rencontré(s) sur une vraie parcelle "
                "mais absent(s) du fichier — signalé(s), AUCUNE colonne insérée (relais manuel Teams requis) :"
            )
            for ev in self.colonnes_creees_detail:
                lignes.append(f"  - code '{ev.code}' (famille '{ev.color_family_id}')")
        elif self.colonnes_creees:
            # Repli si seuls les codes sont connus (pas d'évènement
            # détaillé disponible) — ne devrait plus arriver en pratique
            # une fois tous les appelants à jour, gardé pour compatibilité.
            lignes.append(
                f"{len(self.colonnes_creees)} code(s) de zone rencontré(s) mais absent(s) du fichier — "
                "signalé(s), AUCUNE colonne insérée (relais manuel Teams requis) : "
                + ", ".join(self.colonnes_creees)
            )
        non_resolues = {c for r in self.resultats_par_rue for c in r.colonnes_non_resolues}
        if non_resolues:
            lignes.append(
                f"{len(non_resolues)} colonne(s) non résolue(s), laissées vides : "
                + ", ".join(sorted(non_resolues))
                + " — à classer dans le registre de colonnes."
            )
        # Compte GLOBAL (tout le fichier, tous runs confondus) si connu
        # (voir cellules_erreur_fichier) — sinon repli sur le compte de
        # CE run seulement, pour rester rétrocompatible avec un appelant
        # qui ne le renseigne pas.
        n_erreur = self.cellules_erreur_fichier if self.cellules_erreur_fichier is not None else self.total_cellules_erreur
        n_manuel = self.cellules_manuelles_fichier if self.cellules_manuelles_fichier is not None else self.total_cellules_manuelles
        portee = "dans le fichier" if self.cellules_erreur_fichier is not None else "lors de ce run"
        if n_erreur:
            lignes.append(
                f"{n_erreur} cellule(s) en \"ERREUR\" {portee} (règle existante, échec "
                "ponctuel) — récupérables via le bouton \"Retraiter les erreurs\"."
            )
        if n_manuel:
            lignes.append(
                f"{n_manuel} cellule(s) marquée(s) \"Manuellement\" {portee} (aucune "
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
