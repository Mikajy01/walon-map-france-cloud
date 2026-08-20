"""Correspondance icône -> catégorie officielle `du-categories` pour le
bloc "fiche d'information détaillée" du gabarit (colonnes AD→EN dans
"en Tête Off 6.xlsx" au moment de la génération — la LETTRE n'a aucune
importance ici, seul le hash d'icône compte, voir le plan).

Généré une fois par correspondance floue (`utils.text_normalize.
meilleure_correspondance`) entre chaque en-tête du gabarit officiel et
les 277 catégories renvoyées par `/standard/du-categories`, score ≥ 0.90
uniquement, ET après avoir explicitement écarté toute icône dont le hash
serait partagé par plusieurs en-têtes réellement différents dans le
gabarit (aucun cas trouvé pour ce bloc précis, contrairement au bloc SUP
— voir `services/excel_service.py::bootstrap_from_template`, qui gère ce
cas différemment, par extraction de code depuis le texte plutôt que par
table figée, car un équivalent déterministe existe pour les codes SUP
mais pas pour les catégories `du` qui n'ont pas de code court dans le
texte de l'en-tête lui-même).

Table VIVANTE : à régénérer/étendre si le gabarit officiel change
significativement (nouvelles colonnes, icônes renouvelées) — un icon_hash
absent d'ici reste simplement `pending` (voir le registre de colonnes),
jamais deviné.

Format : `icon_hash -> (type, code)` où `type` ∈ {"information",
"prescription"} et `code` est le code officiel (ex: `"05-00"`)."""

from __future__ import annotations

from typing import Dict, Tuple

DU_MAPPING: Dict[str, Tuple[str, str]] = {
    # Ajoutés le 2026-08-20 : 4 icônes uniques tombées sur le repli
    # `icone::<lettre>` (jamais calculé, voir services/excel_service.py::
    # bootstrap_from_template) lors d'un vrai traitement (commune Argis,
    # 01017) — trouvés en confrontant leur texte réel d'en-tête à
    # `/standard/du-categories` en direct (277 entrées), correspondance
    # non-ambiguë à chaque fois :
    '513ab2fe843efd734a652c5cacd25d10': ('information', '39-00'),  # Périmètres de projets Association Foncière Urbaine de Projet (AFUP)
    '74c6b3487e1983850274320cdb87178a': ('information', '99-00'),  # Autres périmètres d'informations -> "Autre périmètre, secteur, plan, document, site, projet, espace."
    '82809c2c2668c5c3a0f2105fd8585d87': ('prescription', '02-00'),  # Zone inconstructible du PPRi / ... / Limitation de la constructibilité pour des raisons environnementales, de risques, d'intérêt général
    '5cba280fa7ac0d72b22cfa1a33a681a8': ('prescription', '99-00'),  # Autres prescriptions -> "Autre"
    # PAS ajouté : icône '66c1192df348be13e75f97a625506785' (colonne GP,
    # "Installations de navigation et d'atterrissage-Zone primaire de
    # dégagemement-T8") — même famille que les colonnes degagement_secteur/
    # zone_secondaire/zone_speciale déjà documentées ailleurs comme sans
    # source : re-vérifié en direct (2026-08-20) contre `/standard/
    # du-categories` (277) ET `/standard/sup-categories` (66), aucune
    # entrée ne couvre les zones de dégagement aéronautique civil (T8) —
    # toujours non câblé, jamais deviné.
    '0412d50109f3a6ee1e09d4a6295fac1f': ('prescription', '30-00'),  # Majoration des volumes constructibles
    '0450ae9c217fe1688dee52afe5dd1d2d': ('prescription', '41-00'),  # Aspect extérieur
    '04fc6c05acd88b96412a1d4ac8143e9c': ('prescription', '39-50'),  # Hauteur maximale de façade
    '062dea212f0b2fe4d5c14d9e8bb2762d': ('prescription', '24-00'),  # Voies, chemins, transport public à conserver et à créer
    '1281627001f7d087e9ca8d3562a0526c': ('information', '24-00'),  # Document d'aménagement artisanal et Commercial
    '142624218da56d12db4a8fde31467b6c': ('prescription', '40-50'),  # Point de vue, perspective à préserver et à mettre en valeur
    '18b23d76aa44452d13139b3b0e47f468': ('prescription', '32-00'),  # Exclusion protection de plans d'eau de faible importance
    '1a57f96bd0da37282226ff3bcc02cc4c': ('prescription', '06-00'),  # Secteur à densité maximale pour les reconstructions ou aménagements de bâtiments existants
    '1bbf5d55b49c205b32541dee3755968c': ('information', '23-00'),  # Arrêté du préfet coordonnateur de massif
    '26e33600a5c9f29bd36c92da93c280cf': ('information', '25-00'),  # Périmètre de protection des espaces agricoles et naturels péri-urbains
    '274a1401223a92ad144d17c486050b75': ('prescription', '07-55'),  # Séquence, composition, ordonnance architecturale ou urbaine protégée
    '2a2365d20c79deeeca8a70606da2a421': ('prescription', '28-00'),  # Conditions de desserte
    '2b7456c2a499b9513ed7c6b8ce8f7a9b': ('information', '21-00'),  # Projet de plan de prévention des risques
    '2f9204ffda1da5e76dd8b6ed0c418eec': ('information', '17-00'),  # Zone à risque d'exposition au plomb
    '33a0a80f825823094b095bb739bed43f': ('prescription', '15-00'),  # Règles d'implantation des constructions
    '35170aaa92391a117638b5f4699655e4': ('information', '16-00'),  # Site archéologique
    '388f2bfd6efc8b42ccf8eb105164a4ec': ('prescription', '15-51'),  # Limite imposée d'implantation de construction
    '3a775435182d53b728e23db228e221a4': ('prescription', '17-00'),  # Secteur à programme de logements mixité sociale en zone U et AU
    '420bdc706b1eeb77f608d3a49381db6b': ('information', '30-00'),  # Périmètre projet urbain partenarial
    '4b748b064bd4d6c515ea40736b50b183': ('information', '32-00'),  # Secteur de taxe d'aménagement
    '4ec040ad8e11c600160d1ecb128fa8f6': ('prescription', '50-00'),  # Interdiction types d'activités, destinations, sous-destinations
    '536e65959ec6ba9bc4e50781e50d973a': ('prescription', '47-00'),  # Desserte par les réseaux
    '5d2ca1268e0784c822f06c9049b9173f': ('information', '22-00'),  # Protection des rives des plans d'eau en zone de montagne
    '5e6b98869e3aad042fdd84faa09a22a6': ('information', '26-00'),  # Lotissement
    '64e6e9cbeed0e633773bc55dc57f4b3f': ('prescription', '24-50'),  # Passage ou liaison piétonne à maintenir ou à créer
    '6867dc02b25a2cc8ae338940124c54f3': ('prescription', '39-52'),  # Hauteur imposée de façade
    '6b8cff019ddf6303e59687cdbdf1e382': ('information', '35-00'),  # Périmètre de secteur affecté par un seuil minimal de densité
    '6dfb5623df0cb8483da054e1d73e0fb8': ('information', '27-00'),  # Plan d'exposition au bruit des aérodromes
    '702dbbe88bd4c78dbca8d7053fd0f34a': ('information', '14-00'),  # Périmètre de voisinage d'infrastructure de transport terrestre
    '70824b41f9e75b498f01589cd3cc0d70': ('information', '09-00'),  # Périmètre minier de concession pour l'exploitation ou le stockage
    '71dbb2cf2cacbb40a65e4e3b0151b6a0': ('prescription', '07-53'),  # Mur de soutènement, rempart ou mur de clôture protégé
    '736ebf986166551341cf0ce62aa4fa8f': ('prescription', '05-00'),  # Emplacement réservé
    '746e8d6ab182c5dcbda8e43e67f1076c': ('prescription', '07-59'),  # Séquence, composition ou ordonnance végétale d'ensemble protégée
    '7677d16d368f53e180d3de30e7361b91': ('prescription', '07-51'),  # Elément intérieur particulier protégé
    '7d194c717ccdb6fd33f7a28abc1dbe7d': ('information', '70-00'),  # Emprise ou localisation des immeubles bâtis classés monuments historiques
    '80a0aea2ba279f1f4bc7f5622d1afcdf': ('prescription', '22-00'),  # Diversité commerciale à protéger ou à développer
    '840dc51b65e898a308b6570d79bbabce': ('prescription', '20-00'),  # Secteur à transfert de constructibilité en zone N
    '869bb34878f48f930dd3987c21a4fccd': ('information', '07-00'),  # Périmètre de développement prioritaire économie d'énergie
    '87880599540a151350a9e894d9be3485': ('prescription', '42-00'),  # Coefficient de biotope par surface
    '87c647d72fe5070232b082705d57a9c0': ('prescription', '07-66'),  # Place, cour, ou autre espace libre à dominante minérale non protégé à requalifier
    '8a8996a5099d113e41529d96bbb93de7': ('information', '11-00'),  # Périmètre des zones délimitées - divisions foncières soumises à déclaration préalable
    '8e5673663ba9182f0e25cea15bef3dcd': ('information', '38-00'),  # Secteurs d'information sur les sols
    '907eb42cb9e10ae960f007ac91828368': ('prescription', '01-01'),  # Espace boisé classé à protéger ou conserver
    '918c5a9893a5f59b7d56b24cb00d4db1': ('information', '05-00'),  # Zone d'aménagement différé
    '9190be32c216968966ef9f7c49a4fe7d': ('prescription', '07-63'),  # Point d'eau ou source protégé
    '9b3886973d65306cfa1281b53b2d2ce6': ('prescription', '03-00'),  # Secteur avec disposition de reconstruction/démolition
    'a11061fd838c891a7748fcb6fcc46647': ('prescription', '34-00'),  # Espaces, paysage et milieux caractéristiques du patrimoine naturel et culturel montagnard
    'a2828d4060c45df7bcda6e0408d0be00': ('prescription', '37-00'),  # Règles différenciées entre le rez-de-chaussée et les étages supérieurs
    'a3659df3066ff5f0a61adbbe55922697': ('prescription', '07-64'),  # Passage d'eau souterrain protégé
    'a60515682f23947cc75b7bcf16f48ae6': ('prescription', '48-00'),  # Mesures pour limiter l'imperméabilisation des sols
    'a8efcae2c8a9ef0be19a92edd58cc76d': ('prescription', '07-60'),  # Arbre remarquable ou autre élément naturel protégé
    'ab72a0ed464e973f5527798b7f58b26b': ('prescription', '01-00'),  # Espaces boisés classés
    'ac5258ec575a55b8adbd67a647fa1e8f': ('prescription', '03-50'),  # Immeuble ou partie d'immeuble dont la modification peut être imposée
    'aed328363ea6fc89ecc8620262cfcc56': ('prescription', '07-51'),  # Elément extérieur particulier protégé
    'b01fa276a2026b1e1738e3018ef803c0': ('prescription', '44-00'),  # Stationnement
    'b1d174ae658b67e7f6dd4ec7596bf6e8': ('prescription', '16-00'),  # Constructions et installations nécessaires à des équipements collectifs en zone A ou N
    'b1e3271c09aa2601338c85ff8c950c85': ('prescription', '33-00'),  # Secteur de dérogation aux protections des rives des plans d'eau en zone de montagne
    'b31d1eae250624d1486a531912be7daa': ('prescription', '07-58'),  # Espace libre à dominante végétale protégé
    'b9e1c709deb8c9fdacf287ae92f374df': ('prescription', '26-00'),  # Secteur de performance énergétique
    'ba85a36a4e163e0a81f016c6ed2a5a76': ('information', '36-00'),  # Schémas d'aménagement de plage
    'bc390c6c0b47f404a85659c47f105308': ('prescription', '35-00'),  # Terres nécessaires au maintien et au développement des activités agricoles
    'bce062b82818da3dd87a902472fc3b3c': ('prescription', '43-00'),  # Réalisation d'espaces libres, plantations, aires de jeux et de loisir
    'bfc2ee2b77acad511206e4e0b10bf28e': ('prescription', '07-57'),  # Parc ou jardin de pleine terre protégé
    'c16d86c93f045dc379ca5dbdbd82c86e': ('prescription', '07-56'),  # Séquence naturelle protégée
    'c1bff8ff352a865f6660c999aa12c723': ('information', '10-00'),  # Zone de recherche et d'exploitation de carrière
    'c7b489d0d70c561fe8cced69ac650b1a': ('prescription', '39-51'),  # Hauteur maximale de faîtage ou de construction
    'c803f7f9921adc0adb5971e6365a9fa6': ('information', '12-00'),  # Périmètre de sursis à statuer
    'c80e98feffdda380227708a37946d26c': ('prescription', '25-00'),  # Éléments de continuité écologique et trame verte et bleue
    'cabc0e2476c484aeb08a18302a3b3999': ('prescription', '13-00'),  # Zone à aménager en vue de la pratique du ski
    'cae15cd6e8f693326a8d64d5cfb7ba04': ('prescription', '23-00'),  # Secteur avec taille minimale des logements en zone U et AU
    'cc7b5e5da29831a0de321d2a0d621702': ('prescription', '14-00'),  # Secteur de plan de masse
    'ce24773891f3d47b4e5f1bae48a99aca': ('prescription', '29-00'),  # Secteur avec densité minimale de construction
    'cee290c4e5beb4ff1e10b63b2db85f89': ('information', '33-00'),  # Droit de préemption commercial
    'd2f6fc026a0bcc9d7e6a4fc2d1a33172': ('information', '31-00'),  # Périmètres patrimoniaux d'exclusion des matériaux et énergies renouvelables
    'd6c950b4d5f36ef47ba37ff7bc4d2b1c': ('prescription', '38-00'),  # Emprise au sol
    'd850ca727601708e4f4b0def2136ef8f': ('prescription', '08-00'),  # Terrain cultivé ou non bâti à protéger en zone urbaine
    'dae7bd63fe6c0e10e97d6a9720a16bd7': ('information', '19-01'),  # Zones d'assainissement collectif/non collectif
    'dfad9739bc8122b192fc898349770d0d': ('prescription', '15-50'),  # Limite maximale d'implantation de construction
    'e61b290756d0a2c2938fa9458ef9cccc': ('prescription', '07-65'),  # Espace vert non protégé à requalifier
    'e67743fcbf3d8fdb5fc8be38ff9f20db': ('information', '37-00'),  # Bois ou forêts relevant du régime forestier
    'e72642b351e0f41cd0b91bd86035ec1f': ('prescription', '51-00'),  # Autorisation sous conditions types d'activités, destinations, sous-destinations
    'e85534f04ec44b8e6b7fbaf1316daf57': ('information', '34-00'),  # Périmètre d'opération d'intérêt national
    'e9bfcf62f6ef69cb0b7e3ebd0e36cb3f': ('prescription', '07-66'),  # Place, cour, ou autre espace libre à dominante minérale non protégé à requalifier
    'ea28de394ee63016139b989e66124b1f': ('prescription', '46-00'),  # Constructibilité espace boisé antérieur au 20ème siècle
    'ea56440f09ad74d489b1a01be7879217': ('prescription', '07-61'),  # Place, cour ou autre espace libre à dominante minérale protégé
    'ea868fb8865891e7fc6fd11ccbfd0d75': ('prescription', '07-65'),  # Espace vert non protégé à requalifier
    'ec8b2655e500abf77c9eb2ad278b75b3': ('information', '06-00'),  # Zone d'obligation du permis de démolir
    'ecef474e747d0249f032824762f87a50': ('prescription', '27-00'),  # Secteur d'aménagement numérique
    'edad618dc1998f0ee626c77cdbc125b0': ('information', '13-00'),  # Secteur de programme d'aménagement d'ensemble
    'f075e4485fc698730204f7fb3f364e94': ('prescription', '07-68'),  # Immeuble non bâti ou espace libre non protégé
    'f58c3d3d195318c537b8e657d6085cf8': ('prescription', '36-00'),  # Mixité des destinations ou sous-destinations
    'f638182f63347ede23981c8277abc8ba': ('information', '15-00'),  # Zone Agricole Protégée
    'fa0cb1c1f95a205b5c04232c297f9af4': ('prescription', '18-00'),  # Périmètre comportant des Orientations d'Aménagement et de Programmation

    # 4 correspondances confirmées en direct sur un vrai fichier traité
    # (Arboys en Bugey) — texte réel = version tronquée du libelong
    # officiel, un seul candidat officiel possible à chaque fois.
    '3bb966723f8aa95e58fd7da0b2272a08': ('information', '08-00'),  # Périmètre forestier : interdiction ou réglementation des plantations
    '678840023b26e2bfb12a2d2537249df5': ('prescription', '07-69'),  # Unité urbanistique ou paysagère soumise à des dispositions spécifiques
    'ae82a2ce4e1a6b494e77e8d626e248a4': ('prescription', '49-00'),  # Opération d'ensemble imposée
    '0d7fd93063c7309ce251970fd19a0768': ('prescription', '04-00'),  # Périmètre issu des plan de déplacements urbains sur obligation de stationnement
    # Résolu grâce à "en Tête Off 8.xlsx" (nouvelle version du gabarit,
    # colonnes ajoutées par les collègues quand ils rencontrent un cas
    # réel absent) : l'en-tête y est plus complet ("Bâtis d'intérêt
    # patrimonial et architectural / Bosquets et haies ou alignements
    # d'arbres / Eléments de paysage" vs juste la 2e moitié dans l'ancien
    # gabarit), même hash d'icône confirmé identique entre les 2
    # fichiers. Le score de correspondance floue automatique reste
    # faible (0,57, aucune candidate ne contient tous les mots), mais la
    # correspondance sémantique est sans ambiguïté : 07-00 est
    # explicitement le seul code couvrant à la fois le motif
    # "culturel/historique/architectural" (bâti patrimonial) ET le motif
    # "écologique" (bosquets/haies/éléments de paysage) dans le MÊME
    # libellé officiel — raisonnement direct, pas une supposition.
    'f09f859cc4811bf9b66c15dc7e300e38': ('prescription', '07-00'),  # Patrimoine bâti, paysager ou éléments de paysages à protéger (motifs culturel/historique/architectural OU écologique)
    'd058f99b34ca5fc33ffeb1319c694cb9': ('information', '01-01'),  # Secteur sauvegardé (PSMV) — déjà connu comme alias texte, l'icône le shadowait

    # 4 correspondances confirmées en direct (Arboys en Bugey), texte
    # complet officiel relu en entier cette fois (le fuzzy-match tronqué
    # à 55 caractères avait fait paraître certaines comme incertaines
    # alors que le texte complet confirme un vrai recouvrement).
    'b20ca5d1c8b545ad2c3135cc46fdcca0': ('information', '18-00'),  # Espaces et milieux à préserver (intérêt écologique)
    'ffc1b546d34794887e69d429522fff8e': ('information', '28-00'),  # Dépassement des règles du PLU (agrandissement/construction/diversité de l'habitat)
    '026180dc467d4538c4d2631b58d2abd4': ('information', '29-00'),  # Dépassement des règles du PLU pour performance énergétique
    '4e5490c60251e2756c9d01511346f077': ('information', '02-00'),  # Zone d'aménagement concerté (le texte réel ajoute "surface de plancher, destination" — même code de base, qualificatif non représentable séparément)
}


# Icônes dont le rôle n'est PAS une catégorie `du-categories` (277
# entrées) mais un concept d'une AUTRE catégorie GPU (`scot`, `mec`) —
# celles-ci n'ont pas de liste officielle de codes comme `du`/`sup`
# (confirmé en direct : `/standard/scot-categories` et `/standard/
# mec-categories` renvoient 404), donc `role_code` ici est un
# identifiant CHOISI par nous, pas un code officiel. Résolu via
# `services/gpu_rules.py::resoudre_scot` (champ `approved` de la réponse
# `feature-info/scot`, confirmé en direct sur une vraie parcelle
# d'Arboys en Bugey — "SCOT BUGEY", `approved: true`).
ROLES_PERSONNALISES_PAR_ICONE: Dict[str, str] = {
    'feb67ebaec9e93c1139330abc4576c8e': 'schema_coherence_territoriale_publie',
    'abe4c9fcc3b7990e8408e6801ca59b7e': 'schema_coherence_territoriale_non_publie',
    '457a78435150ee0b20c970b0c7320d34': 'perimetre_scot_arrete',

    # Codes SUP officiels réels (confirmés en direct dans `/standard/
    # sup-categories`) mais dont le texte de l'en-tête ne permet PAS
    # l'extraction automatique par `_extraire_code_sup` (voir services/
    # excel_service.py) — soit parce que le code apparaît après un
    # ESPACE plutôt qu'un tiret ("...dégagement PT2", pas "...
    # dégagement-PT2"), soit à cause d'une coquille réelle dans le texte
    # (transposition de lettres). Rôle `gpu_sup_<code>` directement
    # (même convention que `bootstrap_from_template`), pour que
    # `resoudre_gpu_detaille` les calcule automatiquement, aucun code
    # supplémentaire nécessaire.
    '70bcb96e99ef9adf71dbad50b8756d41': 'gpu_sup_t2',  # "Transport par câble" = servitude de survol au profit des téléphériques (T2)
    '7098f0a81e2b1db7437a8a91c82fb015': 'gpu_sup_pt3',  # "Réseaux télécommunication-TP3" — coquille confirmée : "TP3" n'existe pas, "PT3" (réseaux de télécommunications) si
    '9c724256db0a153eb76d40fbfc2bead7': 'gpu_sup_pt2',  # "Communications éléctroniques-Zone primaire de dégagement" — code PT2 après un espace, non extrait automatiquement
    '0098d7cbee64f9b55ce911026f02057d': 'gpu_sup_pt2',  # idem, "Zone secondaire, spéciale et secteur de dégagement PT2" — même code PT2, sous-zone non distinguable (comme le bloc T5/T8 aéronautique)
    'efc8fb812584c01265f038deafc9856f': 'gpu_sup_pt2',  # idem (2e occurrence de cette même colonne dans le gabarit)

    # Colonne combinant EXPLICITEMENT 2 codes officiels DISTINCTS avec un
    # "/" ("Zone Humide / Espaces remarquables du littoral") — pas une
    # coquille/reformulation d'UN SEUL concept (contrairement à "Zone
    # naturelle non constructible / Construction non autorisées", qui
    # elle décrit UNE seule chose deux fois). `prescription|31-00`
    # (littoral) et `prescription|31-05` (zones humides) sont deux
    # prescriptions officielles séparées et réelles — le rôle personnalisé
    # ci-dessous déclenche une règle dédiée (`gpu_rules.py::
    # resoudre_zone_humide_ou_littoral`) qui répond "O" si L'UNE OU
    # L'AUTRE s'applique, jamais un seul des deux codes au hasard.
    '3797bd49e22746028a9b91559233d8f5': 'zone_humide_ou_littoral',
}
