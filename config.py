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
    "argiles_exposition_forte": ["Argiles Exposition Forte", "Exposition Forte"],
    "argiles_exposition_moyenne": ["Argiles Exposition Moayen", "Exposition Moayen"],
    "argiles_exposition_faible": ["Argiles Exposition Faible", "Exposition Faible"],
    "radon_categorie_1": ["Catégorie 1"],
    "radon_categorie_2": ["Catégorie 2"],
    "radon_categorie_3": ["Catégorie 3"],
    "sismicite_tres_faible": ["Sismicité très faible"],
    "sismicite_faible": ["Sismicité faible"],
    "sismicite_moderee": ["Sismicité modorée"],
    "sismicite_moyenne": ["Sismicité moyenne"],
    "sismicite_forte": ["Sismicité forte"],
    "anciens_sites_industriels": [
        "Anciens sites industriels et activités de service",
        "Emprises des sites industriels", "ocalisations des sites industriels",
        "Localisation des anciens sites industriels et activités de service",
        "Emprises des anciens sites industriels et activités de service",
    ],
    "installations_nucleaires": ["Installation Industrielles (Installation nucléaire de base (INB))"],
    "cavites_non_minieres": ["Cavités souterraines d'origine non minière"],
    "cavites_non_minieres_non_localisees": ["Cavités souterraine non minières abandonnées non localisée"],

    # Ajoutés lors de l'analyse systématique du bloc Géorisques/PPR (voir
    # services/georisques_rules.py pour la règle associée à chacun, et sa
    # confiance CONFIRMÉ/STRUCTUREL).
    "mouvements_de_terrain": ["Mouvements de terrain"],
    "mouvements_de_terrain_non_localises": [
        "Mouvements de terrain non localisés", "Mouvements des terrain non localisés",
        "Mouvements des terrain non localiés",  # coquille réelle du nouveau gabarit ("localiés")
    ],
    "obligation_legale_debroussaillement": ["(Zonage informatif des obligation légales de debroussaillement"],
    "canalisations_matieres_dangereuses": [
        "Réseaux et canalisation (Canalisations de transport de matières "
        "dangereuses: Gaz, Hydrocarbures, Produits chimiques)"
    ],
    "secteur_information_sols": ["Secteur d'information sur les sols"],
    "servitude_utilite_publique_sols": [
        "Servitudes d'utilité Publique", "Emprises des servitudes d'utilité publique",
    ],
    "sites_pollues_basol": [
        "Site pollués ou potentiellement pollués appelant une action de "
        "pouvoir publics, à titre preventif ou curatif (BASOL)"
    ],
    "remontee_nappes": ["Remontée de nappes"],

    # PPR au niveau PARCELLE (voir services/georisques_rules.py::
    # _ppr_parcelle_existe — confirmé en direct que `longitude`/
    # `latitude` sur gaspar/pprn|pprt|pprm fait une vraie intersection
    # géométrique, testé sur Lyon).
    "ppr_inondation": ["PPR INONDATION", "PPR INONDATION Périmètre -PPRN Risque Inondation"],
    "ppr_littoraux": [
        "PPR LITTORAUX", "PPR LITTORAUX Périmètre -PPRN Risque Inondation- Par sublension marine",
    ],
    "ppr_mouvement_terrain": [
        "PPR Mouvement de terrain", "PPR Mouvement de terrain Périmètre- PPRN Risque Mouvement de terrain",
    ],
    # "PPR Feu de forêt Périmètre-PPRN Risque Avalanche" : coquille bien
    # réelle du nouveau gabarit (suffixe copié-collé d'une autre ligne,
    # confirmé par sa POSITION — 4e sur 8 dans le bloc PPR parcelle,
    # exactement où "Feu de forêt" est attendu) — jamais "corrigée",
    # juste rattachée au bon rôle par sa position et son préfixe.
    "ppr_feu_foret": [
        "PPR Feu de forêt", "PPR Feu de foret", "PPR Feu de forêt Périmètre-PPRN Risque Avalanche",
    ],
    "ppr_avalanche": ["PPR Avalanche", "PPR Avalanche PPRN Risque Avalanche"],
    # CLPA (Carte de Localisation des Phénomènes d'Avalanche) — confirmé
    # en direct via le GeoServer public INRAE (voir services/wfs_clpa_
    # service.py), après que la source initialement référencée
    # (Cartorisque/prim.net) se soit révélée décommissionnée (HTTP 403).
    "temoignages_avalanches": ["Témoignages d'avalanches"],
    "interpretation_phenomenes_passes": ["Interprétation des phénomène passés"],
    "ppr_seisme": ["PPR Seisme", "PPR Seisme PPRN Risque Seisme"],
    "ppr_risque_minier": ["PPR Risque Minier", "PPR Risque Minier PPRT Risque Minier"],
    "ppr_risque_industriel": ["PPR Risque Industriel", "PPR Risque Industriel PPRT Risque Industriel"],

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

    "sup_inondation": ["SUP inondation", "Zone à risque d'inondation entraînant une servitude d'utilité publique"],
    "sup_mouvement_terrain": [
        "SUP Mouvement de terrain",
        "Zone à risque de mouvement de terrain entraînant une servitude d'utilité publique",
    ],
    "sup_feu_foret": [
        "SUP Feu de forêt", "SUP Feu de foret",
        "Zone à risque d'incendie entraînant une servitude d'utilité publique",
    ],
    "sup_avalanche": ["SUP Avalanche", "Zone à risque d'avalanche entraînant une servitude d'utilité publique"],
    "sup_risque_minier": ["SUP Risque Minier", "Zone à risque minier entraînant une servitude d'utilité publique"],
    "sup_eruption_volcanique": [
        "SUP Eruption Volcanique", "Zone à risque volcanique entraînant une servitude d'utilité publique",
    ],
    "sup_phenomenes_meteorologiques": [
        "SUP phénomènes météorologique",
        # "cyclonique" rattaché ici plutôt qu'à un rôle séparé : le
        # cyclone est classé comme "Phénomène lié à l'atmosphère" dans
        # la nomenclature DGPR officielle (confirmé en direct via
        # /gaspar/risques, code "17"), pas une catégorie SUP à part —
        # aucune entrée "SUP cyclone" distincte n'existe dans le gabarit.
        "Zone à risque cyclonique entraînant une servitude d'utilité publique",
    ],
    "sup_risque_industriel": [
        "SUP Risque industriels", "Zone à risque industriel entraînant une servitude d'utilité publique",
    ],

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
    "gpu_du_prescription_31-05": ["Zone Humides", "Périmètre d'application du plan de sauvegarde et mise en valeur"],
    "zone_natura_2000": ["Zone Nature 2000"],
    "zone_urbaine_patrimoniale": ["Zone urbaine Patrimoniale"],
    "gpu_du_prescription_07-52": ["Immeuble bâti dont les parties extérieures sont protégées, à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-62": ["Cours d'eau, réseau hydraulique ou étendue aquatique protégé, à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-67": ["Immeuble bâti non protégé soumis à des dispositions spécifiques ou des règles générales localisées"],
    "gpu_du_information_04-00": [
        "Instauration du droit de préemption Urbain D.P.U / Périmètre droit de préemption urbain",
        "DPU", "D.P.U", "Périmètre de droit de préemption urbain"],
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
    "zone_soustraite_alea_inondation": [
        "Inondation (Zone soustraittes à l'aléa Inondation)", "Zone soustraittes à l'aléa Inondation)",
    ],
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

    # Ajoutés 2026-08-24 (nouveau gabarit "Tableau Geoportail France
    # Off.xlsx") : le texte listé ici est celui du NOUVEAU fichier — ces
    # rôles n'existaient pas avant, voir services/georisques_rules.py
    # pour la règle (2 endpoints jamais câblés jusqu'ici,
    # installations_classees et gaspar_risques, découverts pendant cette
    # migration).
    "cavite_type_cave": ["Cave"],
    "cavite_type_carriere": ["Carrière"],
    "cavite_type_indetermine": ["Indéterminée"],
    "cavite_type_galerie": ["Galerie"],
    "cavite_type_ouvrage_civil": ["Ouvrage Civil"],
    "cavite_type_ouvrage_militaire": ["Ouvrage militaire"],
    "cavite_type_puits": ["Puits"],
    "installation_elevage_bovin": ["Elevage de bovin"],
    "installation_elevage_porcin": ["Elevage de porc"],
    "installation_elevage_volaille": ["Elevage de volaille"],
    "installation_eolienne": ["Eolienne"],
    "installation_industrie": ["Industries"],
    "installation_usine_seveso": ["Usine Seveso"],
    "installation_usine_non_seveso": ["Usine non Seveso"],
    "mouvement_terrain_glissement": ["Glissement"],
    "mouvement_terrain_eboulement": ["Eboulement"],
    "remnappe_debordement_forte": ["Zones potentiellement sujettes aux débordements de nappe fiabilité FORTE"],
    "remnappe_debordement_moyenne": ["Zones potentiellement sujettes aux débordements de nappe fiabilité MOYENNE"],
    "remnappe_debordement_faible": ["Zones potentiellement sujettes aux débordements de nappe fiabilité FAIBLE"],
    "remnappe_debordement_inconnue": ["Zones potentiellement sujettes aux débordements de nappe fiabilité INCONNUE"],
    "remnappe_inondation_cave_forte": ["Zones potentiellement sujettes aux inondations de cave fiabilité FORTE"],
    "remnappe_inondation_cave_moyenne": ["Zones potentiellement sujettes aux inondations de cave fiabilité MOYENNE"],
    "remnappe_inondation_cave_faible": ["Zones potentiellement sujettes aux inondations de cave fiabilité FAIBLE"],
    "remnappe_inondation_cave_inconnue": ["Zones potentiellement sujettes aux inondations de cave fiabilité INCONNUE"],
    "remnappe_aucun_risque_forte": ["Pas de débordement de nappe ni d'inondation de cave fiabilité FORTE"],
    "remnappe_aucun_risque_moyenne": ["Pas de débordement de nappe ni d'inondation de cave fiabilité MOYENNE"],
    "remnappe_aucun_risque_faible": ["Pas de débordement de nappe ni d'inondation de cave fiabilité FAIBLE"],
    "remnappe_aucun_risque_inconnue": ["Pas de débordement de nappe ni d'inondation de cave fiabilité INCONNUE"],
    "installation_nucleaire_cycle_combustible": ["Cycle du combustible"],
    "installation_nucleaire_cycle_combustible_iode": ["Cycle du combustible avec risque iode"],
    "installation_nucleaire_recherche": ["Activités de recherche"],
    "installation_nucleaire_recherche_iode": ["Activités de recherche avec risque iode"],
    "installation_nucleaire_dechets": ["Gestion des déchets radioactifs"],
    "installation_nucleaire_dechets_iode": ["Gestion des déchets radioactifs avec risque iode"],
    "installation_nucleaire_demantelement": ["Démantèlement"],
    "installation_nucleaire_demantelement_iode": ["Démantèlement avec risque iode"],
    "installation_nucleaire_centrale": ["Centrale nucléaire de production d'électricité"],
    "installation_nucleaire_centrale_iode": ["Centrale nucléaire de production d'électricité avec risque iode"],
    "installation_autres_activites_industrielles": ["Autres activités industrielles"],
    "ppr_inondation_commune_prescrit": ["Commune concernée par un PPRN Risque Inondation prescrit"],
    "ppr_inondation_commune_approuve": ["Commune concernée par un PPRN Risque Inondation approuvé"],
    "ppr_submersion_marine_commune_prescrit": [
        "Commune concernée par un PPRN Risque Inondation par submersion marine prescrit",
    ],
    "ppr_submersion_marine_commune_approuve": [
        "Commune concernée par un PPRN Risque Inondation par submersion marine approuvé",
    ],
    "ppr_mouvement_terrain_commune_prescrit": ["Commune concernée par un PPRN Risque Mouvement de terrain prescrit"],
    "ppr_mouvement_terrain_commune_approuve": ["Commune concernée par un PPRN Risque Mouvement de terrain approuvé"],
    "ppr_mouvement_terrain_affaissement_commune_prescrit": [
        "Commune concernée par un PPRN Risque Mouvement de terrain - Affaissements et effondrements "
        "(Cavités souterraines) prescrit",
    ],
    "ppr_mouvement_terrain_affaissement_commune_approuve": [
        "Commune concernée par un PPRN Risque Mouvement de terrain - Affaissements et effondrements "
        "(Cavités souterraines) approuvé",
    ],
    "ppr_mouvement_terrain_tassement_commune_prescrit": [
        "Commune concernée par un PPRN Risque Mouvement de terrain - Tassements différentiels (Argile) prescrit",
    ],
    "ppr_mouvement_terrain_tassement_commune_approuve": [
        "Commune concernée par un PPRN Risque Mouvement de terrain - Tassements différentiels (Argile) approuvé",
    ],
    "ppr_feu_foret_commune_prescrit": ["Commune concernée par un PPRN Risque Feu de forêt prescrit"],
    "ppr_feu_foret_commune_approuve": ["Commune concernée par un PPRN Risque Feu de forêt approuvé"],
    "ppr_avalanche_commune_prescrit": ["Commune concernée par un PPRN Risque Avalanche prescrit"],
    "ppr_avalanche_commune_approuve": ["Commune concernée par un PPRN Risque Avalanche approuvé"],
    "ppr_seisme_commune_prescrit": ["Commune concernée par un PPRN Risque Séisme prescrit"],
    "ppr_seisme_commune_approuve": ["Commune concernée par un PPRN Risque Séisme approuvé"],
    "ppr_eruption_volcanique_commune_prescrit": ["Commune concernée par un PPRN Risque Éruption volcanique prescrit"],
    "ppr_eruption_volcanique_commune_approuve": ["Commune concernée par un PPRN Risque Éruption volcanique approuvé"],
    "ppr_phenomenes_meteorologiques_commune_prescrit": [
        "Commune concernée par un PPRN Risque Phénomènes météorologiques prescrit",
    ],
    "ppr_phenomenes_meteorologiques_commune_approuve": [
        "Commune concernée par un PPRN Risque Phénomènes météorologiques approuvé",
    ],
    "ppr_risque_industriel_commune_prescrit": ["Commune concernée par un PPRN Risque industriel prescrit"],
    "ppr_risque_industriel_commune_approuve": ["Commune concernée par un PPRN Risque industriel approuvé"],

    # Bridge vers des rôles déjà existants (voir REGLES_WFS pour
    # alea_debordement_*, et le rôle "territoire_risque_important_
    # inondation" plus haut) : le nouveau gabarit utilise un texte
    # différent pour la MÊME donnée, jamais un concept différent —
    # "TRI" est l'acronyme officiel de "Territoire à Risque important
    # d'Inondation" (confirmé : le nom des zones réelles testées dans
    # REGLES_WFS, "TRI Vilaine"/"TRI La Rochelle", utilise déjà cet
    # acronyme). "Crue de X probabilité" reprend les 3 mêmes paliers
    # que "Aléa débordement de cours d'eau X" (fréquent/décennal =
    # forte probabilité, moyen/centennal = moyenne, rare/millénial =
    # faible) — jamais la variante submersion (marine), qui n'a pas
    # d'équivalent "Crue" dans le nouveau fichier.
    "territoire_risque_important_inondation": [
        "Inondation (Territoires à risues importants d'inondation)", "Perimètre de TRI",
    ],
    "alea_debordement_frequent": ["Inondation (Aléa débordement de cours d'eau fréquent ou décennal", "Crue de forte probabilité"],
    "alea_debordement_moyen": ["Inondation (Aléa débordement de cours d'eau moyen ou centennal", "Crue de moyenne probabilité"],
    "alea_debordement_rare": ["Inondation (Aléa débordement de cours d'eau rare ou millénial", "Crue de faible probabilité"],
    "ouvrage_protection_inondation": ["Inondation (Ouvrages de protection)", "Ouvrage de protection"],
    "zone_sur_alea_inondation": ["Inondation (Zone de sur-aléa Inondation)", "Zones de sur-aléa inondation"],
    "secteur_information_sols": [
        "Secteur d'information sur les sols", "Emprises des secteurs d'information sur les sols",
    ],
    "cavites_non_minieres_non_localisees": [
        "Cavités souterraine non minières abandonnées non localisée", "Communes avec cavités non localisées",
    ],
    # "Périmètre d'application ... annexes" et "Périmètres de projets
    # AFUP" : score de correspondance DU sous le seuil automatique
    # (texte tronqué/reformulé) mais concept sans ambiguïté (un seul
    # candidat officiel possible à chaque fois, voir gpu_mappings.py
    # pour la 1ère, déjà documentée comme "AFUP").
    "gpu_du_information_97-00": [
        "Périmètre d'application d'une pièce écrite territorialisée relative aux annexes "
        "(liste des annexes, liste des SUP, plan des SUP)",
        "Périmètre d'application d'une pièce écrite territorialisée relative aux annexes",
    ],
    "gpu_du_information_39-00": [
        "Périmètres de projets Association Foncière Urbaine de Projet",
    ],
    "gpu_du_prescription_38-00": ["Emprise au sol"],
    # Ajouts en masse (2026-08-24) : 91 correspondances DU haute
    # confiance (score >= 0.90 contre /standard/du-categories),
    # verifiees en direct -- necessaires car aucune correspondance
    # floue dynamique n'existe reellement dans le pipeline de
    # production (scan_layout n'appelle jamais la couche 4).
    "gpu_du_information_05-00": ["Zone d'aménagement différé"],
    "gpu_du_information_07-00": ["Périmètre de développement prioritaire économie d'énergie"],
    "gpu_du_information_09-00": ["Périmètre minier de concession pour l'exploitation ou le stockage"],
    "gpu_du_information_11-00": ["Périmètre des zones délimitées - divisions foncière soumises à déclaration préalable"],
    "gpu_du_information_12-00": ["Périmètre de sursis à statuer"],
    "gpu_du_information_13-00": ["Secteur de programme d'aménagement d'ensemble"],
    "gpu_du_information_14-00": ["Périmètre de voisinage d'infrastructure de transport terrestre (secteur affecté par le bruit)"],
    "gpu_du_information_16-00": ["Site archéologique"],
    "gpu_du_information_17-00": ["Zone à risque d'exposition au plomb"],
    "gpu_du_information_19-01": ["Zones d'assainissement collectif / non collectif / eaux usées / eaux pluviales, schéma de réseaux eau et assainissement, systèmes d'élimination des déchets"],
    "gpu_du_information_21-00": ["Projet de plan de prévention des risques"],
    "gpu_du_information_22-00": ["Protection des rives des plans d'eau en zone de montagne"],
    "gpu_du_information_23-00": ["Arrêté du préfet coordonnateur de massif"],
    "gpu_du_information_25-00": ["Périmètre de protection des espaces agricoles et naturels péri-urbains"],
    "gpu_du_information_27-00": ["Plan d'exposition au bruit des aérodromes"],
    "gpu_du_information_30-00": ["Périmètre projet urbain partenarial"],
    "gpu_du_information_31-00": ["Périmètres patrimoniaux d’exclusion des matériaux et énergies renouvelables pris par délibération"],
    "gpu_du_information_32-00": ["Secteur de taxe d'aménagement"],
    "gpu_du_information_33-00": ["Droit de préemption commercial"],
    "gpu_du_information_34-00": ["Périmètre d'opération d'intérêt national"],
    "gpu_du_information_35-00": ["Périmètre de secteur afffecté par un seuil minimal de densité"],
    "gpu_du_information_36-00": ["Schémas d'aménagement de plage"],
    "gpu_du_information_37-00": ["Bois ou forêts relevant du régime forestier"],
    "gpu_du_information_40-00": ["Bien inscrit au patrimoine mondial"],
    "gpu_du_information_41-00": ["Bande de recul le long des axes à grande circulation"],
    "gpu_du_information_42-00": ["Secteurs délimités par délibération de l'autorité compétente en matière d'urbanisme, dans lesquels certaines opérations sont soumises à autorisation d'urbanisme"],
    "gpu_du_information_43-00": ["Secteur d’obligation légale de débroussaillement (OLD) en prévention des incendies"],
    "gpu_du_information_70-00": ["Emprise ou localisation des immeubles bâtis ou non bâtis classés ou inscrits au titre des monuments historiques"],
    "gpu_du_prescription_01-00": ["Espace boisé classé"],
    "gpu_du_prescription_01-01": ["Espace boisé classé à protéger ou conserver"],
    "gpu_du_prescription_02-00": ["Limitation de la constructibilité pour des raisons environnementales, de risques, d’intérêt général"],
    "gpu_du_prescription_03-00": ["Secteur avec disposition de reconstruction/démolition"],
    "gpu_du_prescription_05-00": ["Emplacement réservé"],
    "gpu_du_prescription_07-00": ["Patrimoine bâti, paysager ou éléments de paysages à protéger pour des motifs d'ordre culturel, historique, architectural ou écologique"],
    "gpu_du_prescription_07-51": ["Elément extérieur particulier protégé à conserver, restaurer et mettre en valeur", "Elément intérieur particulier protégé, à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-53": ["Mur de soutènemenr, rempart ou mur de clôture protégé, à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-55": ["Séquence, composition, ordonnance architecturale ou urbaine protégée, à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-56": ["Séquence naturelle protégée (front rocheux, falaise, etc.), à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-57": ["Parc ou jardin de pleine terre protégé, à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-58": ["Espace libre à dominante végétale protégé à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-59": ["Séquence, composition ou ordonnance végétale s'ensemble protégée, à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-63": ["Point d'eau ou source protégé, à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-64": ["Passage d'eau souterrain protégé, à conserver, restaurer et mettre en valeur"],
    "gpu_du_prescription_07-65": ["Espace vert non protégé à requalifier"],
    "gpu_du_prescription_07-68": ["Immeuble non bâti ou espace libre non protégé soumis à des dispositions spécifiques ou des règles générales localisées"],
    "gpu_du_prescription_13-00": ["Zone à aménager en vue de la pratique du ski"],
    "gpu_du_prescription_14-00": ["Secteur de plan de masse"],
    "gpu_du_prescription_15-00": ["Règles d'implantation des constructions"],
    "gpu_du_prescription_15-50": ["Limite maximale d'implantation de construction"],
    "gpu_du_prescription_15-51": ["Limite imposée d'implantation de construction"],
    "gpu_du_prescription_16-00": ["Constructions et installations nécessaires à des équipements collectifs en zone A ou N"],
    "gpu_du_prescription_17-00": ["Secteur à programme de logements mixité sociale en zone U et AU"],
    "gpu_du_prescription_18-00": ["Périmètre comportant des orientations d’aménagement et de programmation (OAP)"],
    "gpu_du_prescription_19-00": ["Secteur protégé en raison de la richesse du sol et du sous-sol"],
    "gpu_du_prescription_20-00": ["Secteur à transfert de constructibilité en zone N"],
    "gpu_du_prescription_22-00": ["Diversité commerciale à protéger ou à développer"],
    "gpu_du_prescription_23-00": ["Secteur avec taille minimale des logements en zone U et AU"],
    "gpu_du_prescription_24-50": ["Passage ou liaison piétonne à maintenir ou à créer"],
    "gpu_du_prescription_25-00": ["Éléments de continuité écologique et trame verte et bleue"],
    "gpu_du_prescription_26-00": ["Secteur de performance énergétique"],
    "gpu_du_prescription_27-00": ["Secteur d’aménagement numérique"],
    "gpu_du_prescription_28-00": ["Conditions de desserte"],
    "gpu_du_prescription_29-00": ["Secteur avec densité minimale de construction"],
    "gpu_du_prescription_30-00": ["Majoration des volumes constructibles"],
    "gpu_du_prescription_31-00": ["Espaces remarquables du littoral"],
    "gpu_du_prescription_32-00": ["Exclusion protection de plans d’eau de faible importance"],
    "gpu_du_prescription_33-00": ["Secteur de dérogation aux protections des rives des plans d'eau en zone de montagne"],
    "gpu_du_prescription_34-00": ["Espaces, paysage et milieux caractéristiques du patrimoine naturel et culturel montagnard à préserver"],
    "gpu_du_prescription_35-00": ["Terres nécessaires au maintien et au développement des activités agricoles pastorales et forestières à préserver"],
    "gpu_du_prescription_36-00": ["Mixité des destinations ou sous-destinations"],
    "gpu_du_prescription_37-00": ["Règles différenciées entre le rez-de-chaussée et les étages supérieurs des constructions"],
    "gpu_du_prescription_39-50": ["Hauteur maximale de façade"],
    "gpu_du_prescription_39-51": ["Hauteur maximale de faîtage ou de construction"],
    "gpu_du_prescription_39-52": ["Hauteur imposée de façade"],
    "gpu_du_prescription_40-50": ["Point de vue, perspective à préserver et à mettre en valeur"],
    "gpu_du_prescription_41-00": ["Aspect extérieur"],
    "gpu_du_prescription_42-00": ["Coefficient de biotope par surface"],
    "gpu_du_prescription_43-00": ["Réalisation d’espaces libres, plantations, aires de jeux et de loisir"],
    "gpu_du_prescription_45-00": ["Secteur de ZAC avec surfaces de plancher déterminées"],
    "gpu_du_prescription_46-00": ["Constructibilité espace boisé antérieur au 20ème siècle"],
    "gpu_du_prescription_47-00": ["Desserte par les réseaux"],
    "gpu_du_prescription_48-00": ["Mesures pour limiter l'imperméabilisation des sols"],
    "gpu_du_prescription_50-00": ["Interdiction types d’activités, destinations, sous-destinations"],
    "gpu_du_prescription_51-00": ["Autorisation sous conditions types d’activités, destinations, sous-destinations"],
    "gpu_du_prescription_52-00": ["Infrastructures et équipements logistiques à préserver ou à développer en zones U et AU"],
    "gpu_du_prescription_53-00": ["Dérogation à l’article L.111-6 pour l’implantation des constructions le long des grands axes routiers"],
    "gpu_du_prescription_54-01": ["Zone exposée au recul du trait de côte à l'horizon de trente ans"],
    "gpu_du_prescription_55-01": ["Secteur d’implantation d’installations de production d'énergies renouvelables, et leurs ouvrages de raccordement, soumises à conditions"],
    "gpu_du_prescription_56-00": ["Secteur dans lequel toutes les constructions nouvelles de logements sont à usage exclusif de résidence principale"],
    "alea_debordement_moyen_cc": [
        "Evènement de moyenne probabilité avec prise en compte du changement climatique",
    ],
    # Les 2 ci-dessous étaient déjà des paires connues (icône -> code DU)
    # dans gpu_mappings.py::DU_MAPPING avant même cette migration —
    # simple ajout d'un alias TEXTE pour que le nouveau gabarit (icônes
    # différentes, jamais matchées par hash) résolve quand même via la
    # même identité déjà validée.
    "gpu_du_prescription_99-00": ["Autre", "Autres prescriptions"],
    "gpu_du_information_99-00": [
        "Autre  périmètre, secteur, plan, document, site, projet, espace.",
        "Autres périmètres d'informations",
    ],

    # Rôles SANS AUCUN équivalent dans l'ancien gabarit (494 colonnes) —
    # vérifié en direct (2026-08-24) : correspondance exacte, par
    # inclusion ET floue, toutes nulles (meilleur score flou ~0.5-0.6,
    # du bruit). Contenu réellement nouveau du "Tableau Geoportail
    # France Off.xlsx", jamais une reformulation. Identité résolue ici
    # (texte -> role_code) mais AUCUNE règle de calcul — voir
    # ROLES_SANS_REGLE plus bas pour le détail de l'investigation menée
    # sur chacun avant d'abandonner l'automatisation.
    "clpa_zone_avalanches": ["Zone d'avalanches"],
    "clpa_zone_presumee_avalancheuse": ["Zone présumée avalancheuse"],
    "clpa_degats_souffle": ["Dégâts importants dus au souffle"],
    "clpa_avalanche_localisee": ["Avalanche localisée"],
    "clpa_avalanche_localisee_presumee": ["Avalanche localisée présumée"],
    "clpa_liaison_presumee": ["Liaison présumée entre avalanches"],
    "stations_epuration": ["Stations d'épuration"],
    "eolien_poste_livraison_instruction": ["Postes de livraison appartenant à un parc en instruction"],
    "eolien_poste_livraison_attente_construction": [
        "Postes de livraison appartenant à un parc en attente de construction",
    ],
    "eolien_poste_livraison_construction": ["Postes de livraison appartenant à un parc en construction"],
    "eolien_poste_livraison_exploitation": ["Postes de livraison appartenant à un parc en exploitation"],
    "eolien_poste_livraison_cessation": [
        "Postes de livraison appartenant à un parc en cessation d'activité",
    ],
    "eolien_parc_instruction": ["Parcs éoliens terrestres en instruction"],
    "eolien_parc_attente_construction": ["Parcs éoliens terrestres en attente de construction"],
    "eolien_parc_construction": ["Parcs éoliens terrestres en construction"],
    "eolien_parc_exploitation": ["Parcs éoliens terrestres en exploitation"],
    "eolien_parc_cessation": ["Parcs éoliens terrestres en cessation d'activité"],
    "mouvement_terrain_coulee": ["Coulee"],
    "erosion_berges": ["Erosion des berges"],
    "sup_gaz_naturel": ["Gaz Naturel"],
    "mise_en_compatibilite": ["Mises en compatibilité"],

    # Ajouts (2e passe, test réel bootstrap+scan sur le gabarit construit) :
    # rôles avec une vraie règle nouvellement câblée.
    "cavite_type_souterrain": ["Souterrain"],
    "installation_elevage": ["Elevage"],
    "mouvement_terrain_effondrement": ["Effondrement"],
    "remnappe_eaip": [
        "Remontée de nappes (Enveloppes Approchées des Innondations Potentielles en cours d'eau "
        "et submersion marine de plus d'un hectare)",
    ],

    # Identité classée, SANS règle (voir ROLES_SANS_REGLE) — 2e passe :
    "clpa_avalanche": ["Avalanche"],
    "remnappe_masq_bdlisa": [
        "Remontée de nappes (Entités hydrogéologiques imperméables à l'affleurement)",
    ],
    "installation_produits_chimiques": ["Produits Chimiques"],
    "installation_hydrocarbures": ["Hydrocarbures"],
    "eolien_appartenant_parc_instruction": ["Eoliennes appartenant à un parc en instruction"],
    "eolien_appartenant_parc_attente_construction": [
        "Eoliennes appartenant à un parc en attente de construction",
    ],
    "eolien_appartenant_parc_construction": ["Eoliennes appartenant à un parc en construction"],
    "eolien_appartenant_parc_exploitation": ["Eoliennes appartenant à un parc en exploitation"],
    "eolien_appartenant_parc_cessation": ["Eoliennes appartenant à un parc en cessation d'activité"],
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

    # -- Bloc "Tableau Geoportail France Off.xlsx" (2026-08-24) : 21
    # colonnes réellement nouvelles (aucun équivalent dans l'ancien
    # gabarit, vérifié en direct), pour lesquelles AUCUNE source fiable
    # n'a été trouvée malgré une investigation réelle sur chacune —
    # jamais deviné, jamais laissé "non résolu" (mystère) non plus :
    # l'identité est classée, seule la règle de calcul manque.
    #
    # Avalanches CLPA (6) — la légende officielle (PDF gouvernemental
    # MEDDE-ONF-Irstea, ET les images de légende du visualiseur public
    # map.avalanches.fr) confirme le VOCABULAIRE de ces 6 catégories,
    # mais reste un pictogramme (couleur/motif de hachure), jamais une
    # table numérique. Les couches WFS réelles qui les portent
    # (clpa_zont/zonpi pour les zones, clpa_lint/linpi découvertes en
    # investigation — jamais utilisées avant — pour les lignes)
    # exposent un champ `CODE`/`RuleID` numérique (1, 2, 3, 7, 8...
    # confirmés en direct) mais AUCUNE des sources consultées
    # (GetCapabilities, DescribeFeatureType, GetLegendGraphic, le jeu de
    # données data.gouv.fr — téléchargement bloqué derrière une page JS
    # non accessible par requête simple) ne documente la correspondance
    # code -> catégorie. Deviner cette table (ex: "CODE 1 = Avalanche"
    # par simple ordre d'apparition dans la légende) aurait été une pure
    # supposition, jamais vérifiée.
    "clpa_zone_avalanches",
    "clpa_zone_presumee_avalancheuse",
    "clpa_degats_souffle",
    "clpa_avalanche_localisee",
    "clpa_avalanche_localisee_presumee",
    "clpa_liaison_presumee",
    #
    # Éolien - cycle de vie (10) — 3 sources réelles indépendantes
    # consultées, aucune n'expose la granularité "instruction/attente de
    # construction/construction" à l'échelle du projet individuel :
    # `installations_classees.etatActivite` (endpoint Géorisques, déjà
    # câblé cette session) n'a que 2 valeurs réelles observées sur un
    # large échantillon ("En exploitation avec titre", "En fin
    # d'exploitation") ; le registre national RTE des installations
    # (ODRE, `registre-national-installation-production-stockage-
    # electricite-agrege`) ne recense QUE les installations déjà
    # raccordées (`regime` = "En service" sur 100% d'un échantillon de
    # 100) ; le suivi des projets en développement RTE (ODRE,
    # `suivi-projet-raccordement-enr`) est agrégé au niveau RÉGION en MW
    # total, sans statut par projet ni localisation. Aucune source
    # publique trouvée pour distinguer "poste de livraison" d'"éolienne"
    # elle-même à ce niveau de détail non plus.
    "eolien_poste_livraison_instruction",
    "eolien_poste_livraison_attente_construction",
    "eolien_poste_livraison_construction",
    "eolien_poste_livraison_exploitation",
    "eolien_poste_livraison_cessation",
    "eolien_parc_instruction",
    "eolien_parc_attente_construction",
    "eolien_parc_construction",
    "eolien_parc_exploitation",
    "eolien_parc_cessation",
    #
    # Isolés (5) — chacun vérifié séparément, aucune source trouvée :
    # "Stations d'épuration" (aucune installation ICPE de ce type
    # trouvée dans les échantillons `installations_classees` testés,
    # aucun code DU/SUP correspondant) ; "Coulee" (le code DGPR officiel
    # le plus proche, "114 - Par ruissellement et coulée de boue", est
    # classé sous Inondation, pas Mouvement de terrain comme Glissement/
    # Eboulement — rattachement réellement ambigu, jamais choisi au
    # hasard) ; "Erosion des berges" (aucune entrée DU/DGPR trouvée) ;
    # "Gaz Naturel" (4 codes SUP réels et pertinents trouvés — I1, I3,
    # I5, I7 — mais aucun moyen de choisir lequel sans deviner, le texte
    # du gabarit ne contient aucun code) ; "Mises en compatibilité"
    # (terme procédural générique de l'urbanisme français, aucune
    # catégorie DU/SUP dédiée trouvée).
    "stations_epuration",
    "mouvement_terrain_coulee",
    "erosion_berges",
    "sup_gaz_naturel",
    "mise_en_compatibilite",

    # -- 2e passe (test réel bootstrap+scan sur le gabarit construit,
    # 2026-08-24) : gaps révélés par le VRAI pipeline (le script
    # d'analyse préalable simulait un matching flou qui n'existe pas
    # réellement dans scan_layout) :
    # "Avalanche" (bare, sans "Zone" ni "Zone présumée") : la légende
    # CLPA officielle confirme que c'est une VRAIE catégorie distincte
    # (avalanche identifiée par numéro via témoignage), même limite que
    # les 6 autres catégories CLPA déjà classées plus haut — pas de
    # table numérique CODE trouvée.
    "clpa_avalanche",
    # "Remontée de nappes (Entités hydrogéologiques imperméables à
    # l'affleurement)" : la source EXISTE et a été identifiée avec
    # certitude — couche WFS BRGM `MASQ_BDLISA`, titre officiel
    # confirmé en direct via GetCapabilities, correspondance EXACTE mot
    # pour mot. MAIS le serveur renvoie une erreur SQL 500 sur CETTE
    # couche précise, à chaque coordonnée testée (4 régions différentes,
    # avec et sans le paramètre `count`) — contrairement à `MASQ_EAIP`
    # (même serveur, couche voisine) qui fonctionne normalement. Un vrai
    # bug serveur, pas une question de source introuvable : à revisiter
    # si ce bug est un jour corrigé côté BRGM.
    "remnappe_masq_bdlisa",
    # "Produits Chimiques"/"Hydrocarbures" (bare) : le seul endpoint
    # Géorisques déjà câblé pour les matières dangereuses (`gaspar_tim`,
    # rôle `canalisations_matieres_dangereuses`) ne renvoie qu'un flag
    # d'existence par commune, sans détail de substance — vérifié en
    # direct sur un enregistrement réel (Arbent). Les codes SUP les plus
    # proches (I1/I3/I5/I7, "gaz naturel, hydrocarbures et produits
    # chimiques") mélangent les 3 substances dans un même code, aucun
    # moyen de les distinguer sans deviner.
    "installation_produits_chimiques",
    "installation_hydrocarbures",
    # "Eoliennes appartenant à un parc en X" : 3e cluster de cycle de
    # vie éolien distinct de "Postes de livraison"/"Parcs éoliens
    # terrestres" déjà documentés plus haut — même investigation, même
    # conclusion (aucune des 3 sources réelles consultées n'expose
    # cette granularité par projet).
    "eolien_appartenant_parc_instruction",
    "eolien_appartenant_parc_attente_construction",
    "eolien_appartenant_parc_construction",
    "eolien_appartenant_parc_exploitation",
    "eolien_appartenant_parc_cessation",
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
