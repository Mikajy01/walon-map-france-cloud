"""Configuration centrale du projet : chemins, paramètres réseau, et URLs
des APIs publiques françaises utilisées (cadastre/urbanisme IGN,
Géoportail de l'urbanisme, Géorisques, géocodage BAN, communes).

Copie autonome de walon-map-france/config.py (voir le plan cloud,
2026-08-20 : "copie complète et autonome", pas de dépendance croisée
entre les deux projets). Diffère de l'original sur exactement 2 points,
propres au contexte CI headless :
- `TEMPLATE_PATH` pointe DANS le repo (`templates/gabarit_officiel.xlsx`,
  committé), pas sur un fichier sibling hors-repo comme côté desktop.
- `STATE_DIR` est nouveau : n'existe pas côté desktop, où l'utilisateur
  choisit lui-même son fichier Excel de travail à chaque run.

Tout le reste (URLs d'API, ROLES_CANONIQUES_VALIDES, COLOR_FAMILY_
ANCHORS, GEORISQUES_ENDPOINTS) doit rester IDENTIQUE à l'original — ce
sont des règles métier vérifiées en direct sur de vraies données, pas
des détails d'environnement. Toute correction faite d'un côté doit être
reportée manuellement de l'autre (voir le plan : compromis accepté pour
la simplicité d'une copie autonome plutôt qu'un paquet partagé).
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Version de l'application
# ---------------------------------------------------------------------------

APP_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# Committé dans le repo (voir templates/) — nécessaire pour amorcer le
# registre ET comme point de départ d'un "nouveau traitement".
TEMPLATE_PATH = BASE_DIR / "templates" / "gabarit_officiel.xlsx"
CACHE_DIR = BASE_DIR / "cache"
LOGS_DIR = BASE_DIR / "logs"
REGISTRY_DIR = BASE_DIR / "registry_data"

# Un fichier Excel par commune traitée (voir main.py::chemin_etat_commune)
# — committé dans le repo, c'est la source de vérité "continuer" entre
# deux runs GitHub Actions (voir le plan : pas de base de progression
# séparée, l'Excel EST la progression).
STATE_DIR = BASE_DIR / "state"

# Fichier de suivi (CSV, append-only) des cellules forcées à "N" faute de
# règle applicable pour cette parcelle précise — décision explicite de
# l'utilisateur (2026-08-18) : jamais de cellule vide, mais chaque repli
# reste tracé pour revisite manuelle si une source de données est trouvée
# plus tard. Voir main.py::_forcer_valeurs_manquantes_en_n.
CELLULES_A_REVISITER_PATH = REGISTRY_DIR / "cellules_a_revisiter.csv"

# Fichier de suivi (texte, append-only) des colonnes créées par la Phase
# A — décision explicite de l'utilisateur (2026-08-19) : cette
# information est trop importante pour rester mélangée au flux de log
# général, elle a son propre canal ET son propre fichier, jamais dans
# logs/. Voir services/excel_service.py::ensure_columns_for_codes,
# main.py::executer_phase_a.
COLONNES_CREEES_LOG_PATH = REGISTRY_DIR / "colonnes_creees.log"

# ---------------------------------------------------------------------------
# Paramètres réseau
# ---------------------------------------------------------------------------

MAX_REQUESTS_PER_SECOND = 5.0
HTTP_TIMEOUT_SECONDS = 30
HTTP_MAX_ATTEMPTS = 5
DEBUG = False  # surchargé par l'option --debug de main.py

SERVICE_TIMEOUT_SECONDS_OVERRIDES: dict[str, int] = {}
SERVICE_MAX_ATTEMPTS_OVERRIDES: dict[str, int] = {}

# ---------------------------------------------------------------------------
# APIs publiques françaises (toutes vérifiées en direct, voir le plan)
# ---------------------------------------------------------------------------

APICARTO_BASE = "https://apicarto.ign.fr/api"
GPU_API_BASE = "https://www.geoportail-urbanisme.gouv.fr/api"
GEORISQUES_API_BASE = "https://www.georisques.gouv.fr/api/v1"
GEOCODAGE_BASE = "https://data.geopf.fr/geocodage"
COMMUNE_API_BASE = "https://geo.api.gouv.fr"
# Utilisé par CommuneService.lister_voies (découverte automatique des
# rues d'une commune, nouveau côté cloud) — vérifié en direct pendant la
# planification (2026-08-20) : /lookup/{code_insee} renvoie la liste
# complète des voies (voies[].nomVoie), testé sur 01015 (Arboys en
# Bugey, 85 voies, contient "Montée du Mollard" et "Montée de la
# Quoille", deux rues réelles déjà traitées dans ce projet).
ADRESSE_PLATEFORME_BASE = "https://plateforme.adresse.data.gouv.fr"

# Familles de couleur du bloc de zonage (6 ancres), RGB ARGB confirmés en
# investigation live sur le vrai gabarit "en Tête Off 6.xlsx" (colonnes
# N/O/Q/R/T/Z) — constantes structurelles de ce modèle de fichier, pas
# des valeurs à découvrir à l'exécution (contrairement aux icônes/codes,
# qui eux varient et passent par le registre SQLite). Confirmé : les 189
# colonnes du bloc KL→RR matchent chacune EXACTEMENT l'une de ces 6
# couleurs, 0 non matchée.
COLOR_FAMILY_ANCHORS: dict[str, str] = {
    "urbaine": "FFC00000",
    "a_urbaniser": "FFFE7A7A",
    "agricole": "FFFFFF00",
    "naturelle": "FF78B832",
    "secteur_marron": "FF7E0000",
    "construction_interdite": "FFB8F052",
}

# Rôles canoniques pour les colonnes SANS icône ni couleur de famille
# (le gros du bloc Géorisques/PPR, ~84 colonnes) — identifiants STABLES
# choisis par nous, indépendants de tout fichier source. Nécessaire car
# le texte d'en-tête de ces colonnes n'est PAS une identité fiable :
# confirmé en construisant le pipeline, le gabarit officiel a DÉJÀ dérivé
# de TRECY ARBENT.xlsx (colonne "Argiles Exposition Moayen" décalée
# depuis l'insertion d'une nouvelle colonne "Forte" avant elle) — amorcer
# le registre depuis un seul fichier et utiliser son texte comme
# `role_code` produit un identifiant qui casse dès le fichier suivant.
#
# Chaque rôle liste tous les libellés RÉELLEMENT rencontrés (variantes
# orthographiques comprises, ex: "Moayen" — coquille bien réelle du
# gabarit, jamais "corrigée" ici) — la correspondance se fait contre
# CETTE liste (couche "alias" de ColumnRegistryService), pas contre le
# texte brut d'un fichier précis. Liste vivante : à étendre à chaque
# nouvelle colonne validée contre une vraie API (voir le plan) et à
# chaque nouvelle variante de libellé observée dans un fichier réel.
ROLES_CANONIQUES_VALIDES: dict[str, list[str]] = {
    "argiles_exposition_forte": ["Argiles Exposition Forte"],
    "argiles_exposition_moyenne": ["Argiles Exposition Moayen"],
    "argiles_exposition_faible": ["Argiles Exposition Faible"],
    "radon_categorie_1": ["Catégorie 1"],
    "radon_categorie_2": ["Catégorie 2"],
    "radon_categorie_3": ["Catégorie 3"],
    "sismicite_tres_faible": ["Sismicité très faible"],
    "sismicite_faible": ["Sismicité faible"],
    "sismicite_moderee": ["Sismicité modorée"],
    "sismicite_moyenne": ["Sismicité moyenne"],
    "sismicite_forte": ["Sismicité forte"],
    "anciens_sites_industriels": ["Anciens sites industriels et activités de service"],
    "installations_nucleaires": ["Installation Industrielles (Installation nucléaire de base (INB))"],
    "cavites_non_minieres": ["Cavités souterraines d'origine non minière"],
    "cavites_non_minieres_non_localisees": ["Cavités souterraine non minières abandonnées non localisée"],

    # Ajoutés lors de l'analyse systématique du bloc Géorisques/PPR (voir
    # services/georisques_rules.py pour la règle associée à chacun, et sa
    # confiance CONFIRMÉ/STRUCTUREL).
    "mouvements_de_terrain": ["Mouvements de terrain"],
    "mouvements_de_terrain_non_localises": ["Mouvements de terrain non localisés"],
    "obligation_legale_debroussaillement": ["(Zonage informatif des obligation légales de debroussaillement"],
    "canalisations_matieres_dangereuses": [
        "Réseaux et canalisation (Canalisations de transport de matières "
        "dangereuses: Gaz, Hydrocarbures, Produits chimiques)"
    ],
    "secteur_information_sols": ["Secteur d'information sur les sols"],
    "servitude_utilite_publique_sols": ["Servitudes d'utilité Publique"],
    "sites_pollues_basol": [
        "Site pollués ou potentiellement pollués appelant une action de "
        "pouvoir publics, à titre preventif ou curatif (BASOL)"
    ],
    "remontee_nappes": ["Remontée de nappes"],

    # PPR au niveau PARCELLE (voir services/georisques_rules.py::
    # _ppr_parcelle_existe — confirmé en direct que `longitude`/
    # `latitude` sur gaspar/pprn|pprt|pprm fait une vraie intersection
    # géométrique, testé sur Lyon).
    "ppr_inondation": ["PPR INONDATION"],
    "ppr_littoraux": ["PPR LITTORAUX"],
    "ppr_mouvement_terrain": ["PPR Mouvement de terrain"],
    "ppr_feu_foret": ["PPR Feu de forêt", "PPR Feu de foret"],
    "ppr_avalanche": ["PPR Avalanche"],
    # CLPA (Carte de Localisation des Phénomènes d'Avalanche) — confirmé
    # en direct via le GeoServer public INRAE (voir services/wfs_clpa_
    # service.py), après que la source initialement référencée
    # (Cartorisque/prim.net) se soit révélée décommissionnée (HTTP 403).
    "temoignages_avalanches": ["Témoignages d'avalanches"],
    "interpretation_phenomenes_passes": ["Interprétation des phénomène passés"],
    "ppr_seisme": ["PPR Seisme"],
    "ppr_risque_minier": ["PPR Risque Minier"],
    "ppr_risque_industriel": ["PPR Risque Industriel"],

    "ppr_inondation_commune": ["PPR Inondation sur la commune"],
    "ppr_submersion_marine_commune": ["PPR Inondation par submension marine sur la commune"],
    "ppr_mouvement_terrain_commune": ["PPR Mouvement de terrain sur la commune"],
    "ppr_mouvement_terrain_affaissement_commune": [
        "PPR Mouvement de terrain affaissements et effondrements sur la commune"
    ],
    "ppr_mouvement_terrain_tassement_commune": [
        "PPR Mouvement de terrain tassement differentiels sur la commune"
    ],
    "ppr_feu_foret_commune": ["PPR Feu de forêt sur lma commune", "PPR Feu de foret sur lma commune"],
    "ppr_avalanche_commune": ["PPR Avalanche sur la commune"],
    "ppr_seisme_commune": ["PPR Seisme sur la commune"],
    "ppr_eruption_volcanique_commune": ["PPR eruption volcanique sur la commune"],
    "ppr_phenomenes_meteorologiques_commune": ["PPR phénomènes météorologiques sur la commune"],
    "ppr_risque_industriel_commune": ["PPR Risque Industriel sur la commune"],
    # Pas d'entrée "ppr_risque_minier_commune" : le gabarit réel n'a PAS
    # de colonne "PPR Risque Minier sur la commune" (seulement "PPR
    # Risque Minier" tout court, colonne JD — la version PARCELLE,
    # volontairement non câblée, voir le docstring de georisques_rules.py).

    "sup_inondation": ["SUP inondation"],
    "sup_mouvement_terrain": ["SUP Mouvement de terrain"],
    "sup_feu_foret": ["SUP Feu de forêt", "SUP Feu de foret"],
    "sup_avalanche": ["SUP Avalanche"],
    "sup_risque_minier": ["SUP Risque Minier"],
    "sup_eruption_volcanique": ["SUP Eruption Volcanique"],
    "sup_phenomenes_meteorologiques": ["SUP phénomènes météorologique"],
    "sup_risque_industriel": ["SUP Risque industriels"],

    # Catégories GPU `du` confirmées manuellement (analyse directe du
    # texte contre `/standard/du-categories`, pas un score de
    # correspondance floue) pour des colonnes dont l'icône est ABSENTE
    # dans au moins un vrai fichier (`Didi-Arbent.xlsx`) — sans repli
    # alias, ces colonnes resteraient éternellement non résolues dans ce
    # fichier précis alors que leur icône existe et fonctionne dans
    # d'autres (ex. le gabarit officiel). Format du role_code :
    # "gpu_du_<type>_<code>", identique à celui attribué par icône (voir
    # services/excel_service.py::bootstrap_from_template et
    # services/gpu_rules.py::_role_vers_code_du) — les deux chemins de
    # résolution convergent vers le même rôle.
    "gpu_du_information_01-01": ["Secteur sauvegardé"],  # PSMV
    "gpu_du_prescription_31-05": ["Zone Humides"],
    "zone_natura_2000": ["Zone Nature 2000"],
    "zone_urbaine_patrimoniale": ["Zone urbaine Patrimoniale"],
    "gpu_du_prescription_07-52": ["Immeuble bâti dont les parties extérieures sont protégées, à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-62": ["Cours d'eau, réseau hydraulique ou étendue aquatique protégé, à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-67": ["Immeuble bâti non protégé soumis à des dispositions spécifiques ou des règles générales localisées"],
    "gpu_du_information_04-00": [
        "Instauration du droit de préemption Urbain D.P.U / Périmètre droit de préemption urbain",
        "DPU", "D.P.U",
    ],
    "gpu_du_information_03-00": ["Zone de préemption dans un espace naturel et sensible"],
    "schema_coherence_territoriale_publie": ["schéma de Cohérence territoriale(publié)"],
    "schema_coherence_territoriale_non_publie": ["schéma de Cohérence territoriale (non publié)"],
    "perimetre_scot_arrete": ["Périmètre de SCOT arrêté"],
    "gpu_du_information_08-00": [
        "Périmètre forestier : interdiction ou réglementation des plantations, "
        "plantations à réaliser et semis d'essence forestière",
    ],
    "gpu_du_prescription_07-69": ["Unité urbanistique ou paysagère soumise à des dispositions spécifiques"],
    "gpu_du_prescription_49-00": ["Opération d'ensemble imposée"],
    "gpu_du_prescription_04-00": [
        "Périmètre issu des plan de déplacements urbains sur obligation de stationnement",
    ],
    "gpu_du_information_20-00": ["Règlement local de publicité"],
    "gpu_du_information_98-00": ["Périmètre d'annulation partielle du document d'urbanisme"],
    "gpu_du_prescription_03-51": ["Immeuble ou partie d'immeuble dont la démolition peut être imposée à l'occasion d'opérations d'aménagement publiques ou privées"],
    "gpu_du_information_02-00": ["Zone d'aménagement concerté", "Zone d'amenagement concentré"],
    "secteur_ouvert_construction": ["Secteur ouvert à la construction"],
    "secteur_vocation_agricole": ["Secteurs à vocation principale d'activité agricole"],
    "secteur_vocation_naturelle": ["Secteur a vocation principal naturel forestière"],
    "zone_constructible": ["Zone constructible", "zone construcible"],
    "alea_debordement_frequent": ["Inondation (Aléa débordement de cours d'eau fréquent ou décennal"],
    "alea_debordement_moyen": ["Inondation (Aléa débordement de cours d'eau moyen ou centennal"],
    "alea_debordement_rare": ["Inondation (Aléa débordement de cours d'eau rare ou millénial"],
    "alea_submersion_frequent": ["Inondation (Aléa submersion fréquent ou décennal)"],
    "alea_submersion_moyen": ["Inondation (Aléa submersion moyen ou centennal)"],
    "alea_submersion_moyen_cc": ["Inondation (Aléa submersion moyen ou centennal avec prise en compte du changement climatique)"],
    "alea_submersion_rare": ["Inondation (Aléa submersion rare ou millénial)"],
    "alea_ruissellement_frequent": ["Inondation (Aléa ruissellement fréquent ou décennal)"],
    "alea_ruissellement_moyen": ["Inondation (Aléa ruissellement moyen ou centennal)"],
    "alea_ruissellement_rare": ["Inondation (Aléa ruissellement rare ou milléniall)"],
    "ouvrage_protection_inondation": ["Inondation (Ouvrages de protection)"],
    "zone_sur_alea_inondation": ["Inondation (Zone de sur-aléa Inondation)"],
    "zone_soustraite_alea_inondation": ["Inondation (Zone soustraittes à l'aléa Inondation)"],
    "territoire_risque_important_inondation": ["Inondation (Territoires à risues importants d'inondation)"],
    "zone_urbaine": ["Zone urbaine"],
    "zone_a_urbaniser_ouverte": ["Zone à urbaniser ouverte"],
    "zone_a_urbaniser_bloquee": ["Zone à urbaniser bloquée"],
    "zone_agricole": ["Zone agricole"],
    "zone_naturelle": ["Zone naturelle et forestière"],
    "zone_couverte_rnu": ["Zone couverte par le RNU"],
    "secteur_urbanise_dense": ["Secteurs urbanisés LES PLUS DENSES"],
    "secteur_reserve_activites": ["Secteur reservé aux activités"],
    "construction_non_autorisee": [
        "Construction non autorisées",
        "Zone naturelle non constructible / Construction non autorisées",
    ],
    "immeuble_interieur_protege_totalite": [
        "Immeuble bâti dont les parties intérieures sont protégées en totalité, "
        "à conserver, restaurer et mettre en valeur",
    ],
    # "T8" dans ces 4 libellés n'existe PAS dans la liste officielle des
    # 66 codes SUP (confirmé en direct via `/standard/sup-categories`) —
    # coquille du gabarit, le vrai code est "T5" ("Servitudes
    # aéronautiques de dégagement (civile)"). Voir `ROLES_SANS_REGLE`
    # plus bas pour pourquoi ça ne change rien : la donnée T5 est
    # officiellement à restriction défense, jamais disponible à la
    # précision parcelle.
    "degagement_zone_primaire": ["Installations de navigation et d'atterrissage-Zone primaire de dégagemement-T8"],
    "degagement_zone_secondaire": ["Installations de navigation et d'atterrissage-Zone secondaire de dégagement-T8"],
    "degagement_zone_speciale": ["Installations de navigation et d'atterrissage-Zone spéciale de dégagement"],
    "degagement_secteur": ["Installations de navigation et d'atterrissage-Secteur de dégagement-T8"],
    "zones_sans_enquete_terrain": ["Zones sans enquête terrain"],
}

# Rôles dont l'IDENTITÉ est résolue mais pour lesquels AUCUNE règle de
# calcul n'existe ni ne peut raisonnablement exister — décision
# explicite de l'utilisateur (2026-08-21) : `main.py::_forcer_valeurs_
# manquantes_en_n` distingue ce cas ("Manuellement", jamais récupérable
# par un bouton de reprise) d'une VRAIE erreur ponctuelle sur un rôle
# qui A une règle mais a échoué cette fois ("ERREUR", récupérable). Un
# rôle `icone::<lettre>` (repli synthétique) est TOUJOURS dans ce cas
# aussi, détecté par préfixe, pas listé ici un par un.
ROLES_SANS_REGLE: frozenset = frozenset({
    "secteur_urbanise_dense",
    "immeuble_interieur_protege_totalite",
    # degagement_zone_primaire/_secondaire/_speciale/_secteur (bloc
    # "Installations de navigation et d'atterrissage") : CONCLUSION
    # DÉFINITIVE (2026-08-22, pas juste "pas encore trouvé") — le "T8"
    # du gabarit est bien une coquille, le vrai code officiel SUP est
    # "T5" ("Servitudes aéronautiques de dégagement (civile)", confirmé
    # en direct via `/standard/sup-categories`, 66 catégories, T8
    # absent). MAIS la fiche officielle T5 (geoportail-urbanisme.gouv.fr/
    # image/fiche_SUP_T5.pdf, §1.4) précise explicitement : "Cette
    # catégorie de servitude fait l'objet de restriction défense. Les
    # données ne sont pas téléchargeables et ne peuvent être consultées
    # qu'à l'échelle communale ou intercommunale." — la précision
    # PARCELLE requise ici n'est donc jamais accessible, quel que soit
    # l'effort mis dans une règle : pas un problème technique, une
    # restriction officielle assumée par l'administration. VÉRIFIÉ EN
    # DIRECT (2026-08-22) : requête réelle sur une parcelle collée à la
    # piste de la base aérienne militaire d'Ambérieu-en-Bugey (01004, AB
    # 0001) — l'API renvoie bien d'autres SUP (PM1, T1) mais JAMAIS T5,
    # confirmant que l'omission est systématique, pas aléatoire.
    #
    # Piste alternative explorée et ÉCARTÉE (décision explicite de
    # l'utilisateur, 2026-08-22) : certains départements (Meurthe-et-
    # Moselle, Corrèze, Seine-et-Marne, Hautes-Alpes, Haute-Loire, Aude...)
    # publient VOLONTAIREMENT leurs propres zones T5 en open data
    # (data.gouv.fr), hors du GPU — mais aucun jeu trouvé pour l'Ain (01),
    # dont l'aérodrome le plus proche d'Argis (BA278 Ambérieu-en-Bugey)
    # est justement militaire. Bâtir une règle dessus ne couvrirait donc
    # jamais Argis, et demanderait une maintenance fragile département
    # par département (jeux hétérogènes, pas de standard national) pour
    # un bénéfice partiel ailleurs — jugé non rentable.
    "degagement_zone_primaire",
    "degagement_zone_secondaire",
    "degagement_zone_speciale",
    "degagement_secteur",
    "zones_sans_enquete_terrain",
})

# Endpoints Géorisques v1 utilisés (bloc de colonnes risques). Confirmé en
# investigation live : les noms de paramètres sont INCOHÉRENTS d'un
# endpoint à l'autre (la plupart en snake_case `code_insee`, mais
# `gaspar/pprn` utilise `codeInsee` en camelCase, et
# `installations_nucleaires` utilise `longitude`/`latitude` séparés
# plutôt que `latlon`) — chaque méthode de GeorisquesService construit
# donc ses propres paramètres, il n'y a pas d'appelant générique unique.
GEORISQUES_ENDPOINTS: dict[str, str] = {
    "rga": "/rga",
    "radon": "/radon",
    "zonage_sismique": "/zonage_sismique",
    "casias": "/ssp/casias",
    "gaspar_pprn": "/gaspar/pprn",
    "gaspar_pprt": "/gaspar/pprt",
    "gaspar_pprm": "/gaspar/pprm",
    "gaspar_risques": "/gaspar/risques",
    "installations_nucleaires": "/installations_nucleaires",
    "installations_classees": "/installations_classees",
    "cavites": "/cavites",
    "mvt": "/mvt",
    "gaspar_azi": "/gaspar/azi",
    "gaspar_tim": "/gaspar/tim",
    "gaspar_tri": "/gaspar/tri",
    "tri_zonage": "/tri_zonage",
    "resultats_rapport_risque": "/resultats_rapport_risque",
    "ssp": "/ssp",
    "ssp_conclusions_sis": "/ssp/conclusions_sis",
    "ssp_conclusions_sup": "/ssp/conclusions_sup",
    "old": "/old",
}
