"""Table déclarative des règles de résolution du bloc Géorisques/PPR —
une petite fonction dédiée par `role_code` (voir
`config.ROLES_CANONIQUES_VALIDES`), plutôt qu'un unique bloc de code
toujours plus long dans `main.py` — évolution anticipée dès la
conception initiale (voir le plan) une fois qu'un nombre significatif de
colonnes est câblé.

Chaque règle est une fonction `(cx, cy, code_insee, georisques) ->
"O"/"N"/None`. `None` = aucune réponse exploitable, la colonne reste
vide plutôt que devinée (jamais "N" par défaut si l'appel échoue ou ne
tranche pas).

IMPORTANT — deux niveaux de confiance bien distincts, marqués sur
chaque règle :
  - CONFIRMÉ : testé en direct contre une vraie valeur "O" connue d'un
    fichier réel (voir le plan/l'historique de la session).
  - STRUCTUREL : correspondance raisonnée entre le nom de la colonne et
    le nom/la documentation de l'endpoint, mais JAMAIS testée contre une
    vraie valeur "O" (aucun exemple positif disponible dans les fichiers
    réels analysés) — à confirmer dès qu'un exemple réel apparaît.

Colonnes volontairement NON câblées ici (aucune règle, restent non
résolues) — jamais devinées faute de correspondance fiable :
  - "Témoignages d'avalanches" / "Interprétation des phénomène passés" /
    "Zones sans enquête terrain" : ce trio correspond très probablement à
    la typologie CLPA (Carte de Localisation des Phénomènes
    Avalancheux — témoignage / interprétation photo / enquête de
    terrain, méthodologie française réelle et documentée), MAIS ce jeu de
    données n'est exposé NI par les 30 endpoints Géorisques v1 (aucun
    layer WFS "avalanche" hors PPR), NI par le catalogue WMS Géoportail
    IGN (935 couches scannées en direct, 0 correspondance) — vérifié,
    pas supposé. Source probable : avalanches.fr (ANENA/Météo-France),
    HORS des 4 sources autorisées pour ce projet — à statuer avec
    l'utilisateur avant d'y toucher.
  - Le bloc "PPR <risque>" SANS "sur la commune" (parcelle précise,
    ex "PPR INONDATION", "PPR LITTORAUX") : nécessite une intersection
    géométrique entre la parcelle et le zonage réglementaire du PPR
    (`zonageReglementaire`, présent dans `gaspar_pprn`/`pprt`/`pprm`
    mais jamais testé au niveau géométrie précise cette session) — le
    déclarer "sur la commune" serait FAUX (une parcelle peut être hors
    zone réglementée même si un PPR existe quelque part sur la
    commune), donc laissé non résolu plutôt que mal résolu.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from services.georisques_service import GeorisquesService
from utils.text_normalize import normaliser

RegleGeorisques = Callable[[float, float, str, GeorisquesService], Optional[str]]


# -- Argiles (CONFIRMÉ : rga, exact sur 2 valeurs réelles différentes) --

def _rga_expose(mot_cle: str) -> RegleGeorisques:
    def regle(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
        rga = g.get_rga(cy, cx)
        if not rga:
            # "N", pas `None` — décision explicite de l'utilisateur
            # (2026-08-23) : la cartographie RGA du BRGM couvre TOUT le
            # territoire français, y compris les zones sans exposition
            # ("exposition nulle") — l'API renvoie alors un corps VIDE
            # plutôt qu'un enregistrement explicite `{"exposition":
            # "nulle"}` (écart réel trouvé en investigation live, Arbigny
            # 01016, 2026-08-22 : HTTP 200, corps vide, à des points
            # réels). C'est une réponse structurelle, jamais une panne :
            # une VRAIE panne réseau/API lève une exception AVANT ce
            # point (dans `HttpClient`/`get_rga`), rattrapée séparément
            # par `_resoudre_resilient` (voir main.py) — donc arriver
            # ici avec `rga` falsy sans exception signifie toujours
            # "zone cartographiée comme non exposée", jamais deviné.
            return "N"
        exposition = (rga.get("exposition") or "").lower()
        return "O" if mot_cle in exposition else "N"
    return regle


# -- Radon (CONFIRMÉ) --

def _radon_categorie(numero: int) -> RegleGeorisques:
    def regle(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
        radon = g.get_radon(code_insee)
        if not radon:
            return None
        return "O" if radon.get("classe_potentiel") == str(numero) else "N"
    return regle


# -- Sismicité (CONFIRMÉ sur "modérée", même endpoint pour les 4 autres niveaux) --

def _sismicite(mot_cle: str) -> RegleGeorisques:
    def regle(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
        sismique = g.get_zonage_sismique(cy, cx)
        if not sismique:
            return None
        libelle = (sismique.get("zone_sismicite") or "").lower()
        return "O" if mot_cle in libelle else "N"
    return regle


# -- Existence simple (liste non vide = "O") --

def _existence_casias(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
    """CONFIRMÉ (site réel retrouvé sur la bonne rue en investigation live)."""
    return "O" if g.get_casias(cy, cx, rayon=200) else "N"


def _existence_mvt(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
    """STRUCTUREL — endpoint `mvt` (mouvements de terrain répertoriés),
    jamais renvoyé de résultat non vide sur les communes testées."""
    return "O" if g.get_mvt(cy, cx, rayon=200) else "N"


def _existence_mvt_non_localise(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
    """CONFIRMÉ (positif) sur la commune 05062 (Hautes-Alpes, hors
    fichiers réels Arbent qui n'ont aucun mouvement de terrain répertorié
    — pas d'exemple positif possible sur les données du projet
    lui-même) : `precision_lieu` (champ réel du schéma `MvtModel`,
    valeurs observées en direct : "Mètre", "Décamètre", "Hectomètre",
    "Commune") vaut "Commune" quand la localisation précise du mouvement
    est inconnue (seule la commune est connue) — lecture directe de "non
    localisé", vérifiée renvoyer "O" sur un vrai enregistrement de ce
    type. Niveau COMMUNE (`get_mvt_commune`, pas un rayon autour d'un
    point) : la colonne elle-même n'a pas de pendant "sur la commune"
    séparé, donc pas d'ambiguïté à trancher contrairement au bloc PPR."""
    enregistrements = g.get_mvt_commune(code_insee)
    return "O" if any(e.get("precision_lieu") == "Commune" for e in enregistrements) else "N"


def _existence_old(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
    """CONFIRMÉ (Toulon, 83137, arrêté préfectoral réel retrouvé) —
    endpoint `/old` (Obligation Légale de Débroussaillement). Niveau
    commune (`code_insee`) : la colonne du gabarit ne précise pas un
    point, et l'obligation OLD est de toute façon définie par arrêté
    préfectoral à l'échelle communale, pas parcelle par parcelle."""
    return "O" if g.get_old(code_insee=code_insee) else "N"


def _existence_tim(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
    """CONFIRMÉ : `gaspar_tim` renvoie un vrai enregistrement pour
    Arbent (transport de matières dangereuses)."""
    return "O" if g.get_gaspar_tim(code_insee) else "N"


def _existence_cavites_non_localisees(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
    """STRUCTUREL — l'énumération officielle des `type` de cavité
    (confirmée en direct via le paramètre `type` du endpoint : Cave,
    Naturelle, Indéterminé, Ouvrage civil, Puits, Divers, Galerie,
    Carrière, Indice, Ouvrage militaire, Réseau galeries, Souterrain)
    NE CONTIENT AUCUNE catégorie "minière" — tout résultat de cet
    endpoint est donc "non minier" par construction (les cavités
    minières relèvent d'un registre séparé, GEODERIS, non exposé par
    cette API). "Non localisée" faute d'un statut dédié dans la
    réponse : interprété comme coordonnées manquantes (`longitude`/
    `latitude` absentes ou nulles)."""
    cavites = g.get_cavites(code_insee)
    return "O" if any(c.get("longitude") is None or c.get("latitude") is None for c in cavites) else "N"


def _existence_cavites(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
    """CONFIRMÉ : 8 cavités réelles retrouvées pour Arbent en
    investigation live (`code_insee=01014`) — voir aussi
    `_existence_cavites_non_localisees` pour l'énumération officielle
    des types (aucune catégorie minière)."""
    return "O" if g.get_cavites(code_insee) else "N"


def _existence_installations_nucleaires(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
    """STRUCTUREL — endpoint dédié, jamais câblé jusqu'ici (oubli, pas
    un problème de source). Écart réel constaté en investigation
    (fichier TRECY) : une ligne marquée "O" pour cette colonne ne
    trouvait aucune installation via cet endpoint — probable erreur de
    remplissage manuel (même famille que les écarts IS/IC déjà
    confirmés par l'utilisateur), pas une faute de la règle elle-même."""
    return "O" if g.get_installations_nucleaires(cy, cx) else "N"


def _existence_ssp_conclusions_sis(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
    """STRUCTUREL — correspondance de nom forte (`ssp/conclusions_sis` =
    Secteur d'Information sur les Sols), 0 résultat pour Arbent (aucun
    exemple positif disponible pour confirmer)."""
    return "O" if g.get_ssp_conclusions_sis(code_insee) else "N"


def _existence_ssp_conclusions_sup(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
    """STRUCTUREL — même remarque que `_existence_ssp_conclusions_sis`."""
    return "O" if g.get_ssp_conclusions_sup(code_insee) else "N"


def _existence_cavite_type(type_attendu: str) -> RegleGeorisques:
    """CONFIRMÉ (2026-08-24, Argis 01017) : le champ `type` d'une cavité
    (`get_cavites`) matche l'énumération officielle documentée plus haut
    (`_existence_cavites_non_localisees`) — 8 cavités réelles trouvées
    pour Arbent, une avec `type="naturelle"`. Comparaison insensible à
    la casse/aux accents (`normaliser`), le champ réel observé est en
    minuscules alors que le gabarit capitalise ("Naturelle")."""
    def regle(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
        cavites = g.get_cavites(code_insee)
        cible = normaliser(type_attendu)
        return "O" if any(normaliser(c.get("type")) == cible for c in cavites) else "N"
    return regle


def _existence_installation_flag(champ: str) -> RegleGeorisques:
    """STRUCTUREL — `/installations_classees` (jamais câblé avant cette
    investigation, voir `GeorisquesService.get_installations_classees`),
    champ booléen direct sur chaque enregistrement (`bovins`, `porcs`,
    `volailles`, `eolienne`, `industrie`...). Jamais testé contre un
    exemple positif réel (l'unique installation trouvée à Argis a tous
    ces champs à `false`), mais le nom du champ correspond exactement et
    sans ambiguïté au libellé de la colonne."""
    def regle(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
        installations = g.get_installations_classees(code_insee)
        return "O" if any(inst.get(champ) for inst in installations) else "N"
    return regle


def _existence_installation_seveso(veut_seveso: bool) -> RegleGeorisques:
    """CONFIRMÉ (2026-08-24, Saint-Vulbas 01390 — commune du parc
    industriel de la Plaine de l'Ain) : `statutSeveso` n'est PAS un
    simple booléen "présent ou null" — écart réel trouvé en
    investigation live, une installation réelle ("GEORG UTZ") a la
    valeur littérale `"Non Seveso"` (chaîne NON vide), et une autre
    ("ASTR'IN LOGISTIQUE") a `"Seveso seuil haut"`. Un premier jet de
    cette règle basé sur `bool(statutSeveso)` aurait classé À TORT
    "Non Seveso" comme "a un statut Seveso" (une chaîne non vide est
    toujours truthy en Python) — corrigé avant tout déploiement en
    excluant explicitement "Non Seveso" du test de vérité. "Usine
    Seveso" = statut renseigné et différent de "Non Seveso" ; "Usine
    non Seveso" = statut EXACTEMENT "Non Seveso" (jamais `null`, qui
    signifie "non évalué", pas "confirmé non Seveso")."""
    def regle(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
        installations = [i for i in g.get_installations_classees(code_insee) if i.get("industrie")]
        if not installations:
            return "N"
        statuts = [i.get("statutSeveso") for i in installations]
        if veut_seveso:
            trouve = any(s not in (None, "Non Seveso") for s in statuts)
        else:
            trouve = any(s == "Non Seveso" for s in statuts)
        return "O" if trouve else "N"
    return regle


def _existence_risque_dgpr(num_risque: str) -> RegleGeorisques:
    """CONFIRMÉ (2026-08-24) — `/gaspar/risques` (jamais câblé avant
    cette investigation, voir `GeorisquesService.get_gaspar_risques`),
    nomenclature officielle DGPR : Argis (01017), déjà une vraie commune
    du projet, a EFFECTIVEMENT "123" (Eboulement) ET "124" (Glissement
    de terrain) dans sa liste de risques réelle — les deux règles
    renvoient "O" en direct sur ce cas connu, pas juste une
    correspondance de nom plausible."""
    def regle(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
        risques = g.get_gaspar_risques(code_insee)
        return "O" if any(r.get("num_risque") == num_risque for r in risques) else "N"
    return regle


def _existence_ssp_basol(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
    """STRUCTUREL — `ssp` (base) comme candidat le plus proche pour
    "Sites pollués ... BASOL", jamais confirmé contre une vraie valeur
    "O" (0 résultat pour Arbent)."""
    return "O" if g.get_ssp(code_insee) else "N"


# -- Champ imbriqué de resultats_rapport_risque (CONFIRMÉ pour remontée
# de nappe : "present": true retrouvé en direct sur Arbent) --

def _rapport_risque_champ(categorie: str, cle: str) -> RegleGeorisques:
    def regle(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
        rapport = g.get_resultats_rapport_risque(cy, cx)
        if not rapport:
            return None
        section = rapport.get(categorie) or {}
        champ = section.get(cle)
        if champ is None:
            return None
        return "O" if champ.get("present") else "N"
    return regle


# -- PPR/SUP "sur la commune" — existence d'un PPR d'un type donné,
# filtré par mot-clé dans le libellé de la procédure.
#
# CONFIRMÉ en direct (Argis, 01017, 2026-08-21) contre un vrai "O" — et
# un vrai faux négatif trouvé au passage : le PPRN "PPRi et PPRmt
# _Argis" (modeleProcedure "PPRN-Multi", supExists=True, vu sur
# https://www.geoportail-urbanisme.gouv.fr/map/parcel-info/
# 01_017_000_000_ZD_0071/, catégorie SUP combinée "PM1") utilise les
# abréviations officielles "PPRi"/"PPRmt", jamais les mots complets
# "inondation"/"mouvement" — "ppri" ne contient pas "inond", "pprmt" ne
# contient ni "mvt" ni "mouvement", donc `ppr_inondation`/`sup_inondation`
# et `ppr_mouvement_terrain`/`sup_mouvement_terrain` (+ leurs variantes
# "_commune") renvoyaient "N" pour un cas pourtant confirmé "O" sur le
# site officiel. Ces deux abréviations ajoutées aux mots-clés concernés.
def _correspond(rec: dict, mots_cles: Optional[tuple]) -> bool:
    """`mots_cles=None` : aucun filtre, tout enregistrement de la liste
    compte (cas `get_gaspar_pprm`/`pprt`, déjà scopés par nature — un
    PPRM est TOUJOURS un risque minier, filtrer par le mot 'minier' dans
    son libellé serait redondant et fragile si le libellé ne le
    contient pas littéralement)."""
    if mots_cles is None:
        return True
    libelle = f"{rec.get('libPpr', '')} {rec.get('modeleProcedure', '')}".lower()
    return any(mc in libelle for mc in mots_cles)


def _ppr_commune_existe(get_liste: str, mots_cles: Optional[tuple]) -> RegleGeorisques:
    def regle(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
        methode = getattr(g, get_liste)
        enregistrements = methode(code_insee)
        for rec in enregistrements:
            if _correspond(rec, mots_cles):
                return "O"
        return "N"
    return regle


def _ppr_parcelle_existe(get_liste: str, mots_cles: Optional[tuple]) -> RegleGeorisques:
    """Comme `_ppr_commune_existe` mais au niveau PARCELLE (point
    précis, `longitude`/`latitude`) — confirmé en direct (test sur
    Lyon) que ce paramètre fait une vraie intersection géométrique avec
    le zonage réglementaire du PPR, pas juste "un PPR existe quelque
    part sur la commune". Alimente le bloc "PPR <risque>" SANS "sur la
    commune" (colonnes IX→JE), qu'on pensait initialement nécessiter une
    géométrie de zonage récupérée séparément — inutile, l'API la teste
    déjà elle-même."""
    def regle(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
        methode = getattr(g, get_liste)
        enregistrements = methode(lon=cx, lat=cy)
        for rec in enregistrements:
            if _correspond(rec, mots_cles):
                return "O"
        return "N"
    return regle


def _sup_existe_pour_type(get_liste: str, mots_cles: Optional[tuple]) -> RegleGeorisques:
    def regle(cx: float, cy: float, code_insee: str, g: GeorisquesService) -> Optional[str]:
        methode = getattr(g, get_liste)
        enregistrements = methode(code_insee)
        for rec in enregistrements:
            if _correspond(rec, mots_cles) and GeorisquesService.sup_existe(rec):
                return "O"
        return "N"
    return regle


# -- Table complète : role_code -> règle -----------------------------

REGLES_GEORISQUES: Dict[str, RegleGeorisques] = {
    "argiles_exposition_forte": _rga_expose("forte"),
    "argiles_exposition_moyenne": _rga_expose("moyen"),
    "argiles_exposition_faible": _rga_expose("faible"),

    "radon_categorie_1": _radon_categorie(1),
    "radon_categorie_2": _radon_categorie(2),
    "radon_categorie_3": _radon_categorie(3),

    "sismicite_tres_faible": _sismicite("tres faible"),
    "sismicite_faible": _sismicite("faible"),
    "sismicite_moderee": _sismicite("modere"),
    "sismicite_moyenne": _sismicite("moyenne"),
    "sismicite_forte": _sismicite("forte"),

    "anciens_sites_industriels": _existence_casias,
    "mouvements_de_terrain": _existence_mvt,
    "mouvements_de_terrain_non_localises": _existence_mvt_non_localise,
    "obligation_legale_debroussaillement": _existence_old,
    "canalisations_matieres_dangereuses": _existence_tim,
    "installations_nucleaires": _existence_installations_nucleaires,
    "cavites_non_minieres": _existence_cavites,
    "cavites_non_minieres_non_localisees": _existence_cavites_non_localisees,
    "secteur_information_sols": _existence_ssp_conclusions_sis,
    "servitude_utilite_publique_sols": _existence_ssp_conclusions_sup,
    "sites_pollues_basol": _existence_ssp_basol,

    "remontee_nappes": _rapport_risque_champ("risquesNaturels", "remonteeNappe"),

    # PPR au niveau PARCELLE (point précis) — confirmé en direct que
    # `longitude`/`latitude` fait une vraie intersection géométrique
    # (voir `_ppr_parcelle_existe`), pas approximé depuis le niveau
    # commune.
    "ppr_inondation": _ppr_parcelle_existe("get_gaspar_pprn", ("inond", "ppri")),
    "ppr_littoraux": _ppr_parcelle_existe("get_gaspar_pprn", ("submersion", "littora")),
    "ppr_mouvement_terrain": _ppr_parcelle_existe("get_gaspar_pprn", ("mvt", "mouvement", "pprmt")),
    "ppr_feu_foret": _ppr_parcelle_existe("get_gaspar_pprn", ("feu de foret", "feu de forêt")),
    "ppr_avalanche": _ppr_parcelle_existe("get_gaspar_pprn", ("avalanche",)),
    "ppr_seisme": _ppr_parcelle_existe("get_gaspar_pprn", ("seisme", "séisme")),
    "ppr_risque_minier": _ppr_parcelle_existe("get_gaspar_pprm", None),
    "ppr_risque_industriel": _ppr_parcelle_existe("get_gaspar_pprt", None),

    "ppr_inondation_commune": _ppr_commune_existe("get_gaspar_pprn", ("inond", "ppri")),
    "ppr_submersion_marine_commune": _ppr_commune_existe("get_gaspar_pprn", ("submersion", "littora")),
    "ppr_mouvement_terrain_commune": _ppr_commune_existe("get_gaspar_pprn", ("mvt", "mouvement", "pprmt")),
    "ppr_mouvement_terrain_affaissement_commune": _ppr_commune_existe("get_gaspar_pprn", ("affaissement",)),
    "ppr_mouvement_terrain_tassement_commune": _ppr_commune_existe("get_gaspar_pprn", ("tassement",)),
    "ppr_feu_foret_commune": _ppr_commune_existe("get_gaspar_pprn", ("feu de foret", "feu de forêt")),
    "ppr_avalanche_commune": _ppr_commune_existe("get_gaspar_pprn", ("avalanche",)),
    "ppr_seisme_commune": _ppr_commune_existe("get_gaspar_pprn", ("seisme", "séisme")),
    "ppr_eruption_volcanique_commune": _ppr_commune_existe("get_gaspar_pprn", ("volcan",)),
    "ppr_phenomenes_meteorologiques_commune": _ppr_commune_existe("get_gaspar_pprn", ("meteo", "météo")),
    "ppr_risque_industriel_commune": _ppr_commune_existe("get_gaspar_pprt", None),
    # Pas de "ppr_risque_minier_commune" : voir config.ROLES_CANONIQUES_VALIDES,
    # aucune colonne "sur la commune" correspondante dans le vrai gabarit.

    "sup_inondation": _sup_existe_pour_type("get_gaspar_pprn", ("inond", "ppri")),
    "sup_mouvement_terrain": _sup_existe_pour_type("get_gaspar_pprn", ("mvt", "mouvement", "pprmt")),
    "sup_feu_foret": _sup_existe_pour_type("get_gaspar_pprn", ("feu de foret", "feu de forêt")),
    "sup_avalanche": _sup_existe_pour_type("get_gaspar_pprn", ("avalanche",)),
    "sup_risque_minier": _sup_existe_pour_type("get_gaspar_pprm", None),
    "sup_eruption_volcanique": _sup_existe_pour_type("get_gaspar_pprn", ("volcan",)),
    "sup_phenomenes_meteorologiques": _sup_existe_pour_type("get_gaspar_pprn", ("meteo", "météo")),
    "sup_risque_industriel": _sup_existe_pour_type("get_gaspar_pprt", None),

    # -- Ajouts 2026-08-24 (investigation "Tableau Geoportail France
    # Off.xlsx") : cavités par type (champ `type` déjà récupéré par
    # `_existence_cavites`, jamais exploité finement avant), et 2
    # endpoints jamais câblés jusqu'ici (`installations_classees`,
    # `gaspar_risques`) découverts en cherchant une source réelle pour
    # des colonnes du nouveau gabarit qui semblaient "sans source".
    "cavite_type_cave": _existence_cavite_type("Cave"),
    "cavite_type_carriere": _existence_cavite_type("Carrière"),
    "cavite_type_indetermine": _existence_cavite_type("Indéterminé"),
    "cavite_type_galerie": _existence_cavite_type("Galerie"),
    "cavite_type_ouvrage_civil": _existence_cavite_type("Ouvrage civil"),
    "cavite_type_ouvrage_militaire": _existence_cavite_type("Ouvrage militaire"),
    "cavite_type_puits": _existence_cavite_type("Puits"),

    "installation_elevage_bovin": _existence_installation_flag("bovins"),
    "installation_elevage_porcin": _existence_installation_flag("porcs"),
    "installation_elevage_volaille": _existence_installation_flag("volailles"),
    "installation_eolienne": _existence_installation_flag("eolienne"),
    "installation_industrie": _existence_installation_flag("industrie"),
    "installation_usine_seveso": _existence_installation_seveso(True),
    "installation_usine_non_seveso": _existence_installation_seveso(False),

    "mouvement_terrain_glissement": _existence_risque_dgpr("124"),
    "mouvement_terrain_eboulement": _existence_risque_dgpr("123"),
}


# -- Aléa inondation détaillé (WFS, service DIFFÉRENT — voir
# services/wfs_georisques_service.py) : table séparée, role_code ->
# (méthode, intensité) où "méthode" est le nom de la méthode sur
# `WfsGeorisquesService` et "intensité" son 2e argument (`None` pour les
# méthodes qui n'en prennent pas). CONFIRMÉ en direct sur 2 zones
# réelles connues (TRI Vilaine pour le débordement, TRI La Rochelle Île
# de Ré pour la submersion marine) — voir le docstring de
# `wfs_georisques_service.py` pour le détail du mapping type/intensité.
REGLES_REMNAPPE: Dict[str, tuple] = {
    # role_code -> (classe, fiabilite) — voir services/wfs_remnappe_
    # service.py::WfsRemnappeService.classe_fiabilite. fiabilite=None
    # signifie "INCONNUE" (champ fiab_tot absent de la feature, jamais
    # une 4e valeur littérale — non observée sur ~500 features réelles).
    "remnappe_debordement_forte": ("Zones potentiellement sujettes aux débordements de nappe", "FORTE"),
    "remnappe_debordement_moyenne": ("Zones potentiellement sujettes aux débordements de nappe", "MOYENNE"),
    "remnappe_debordement_faible": ("Zones potentiellement sujettes aux débordements de nappe", "FAIBLE"),
    "remnappe_debordement_inconnue": ("Zones potentiellement sujettes aux débordements de nappe", None),
    "remnappe_inondation_cave_forte": ("Zones potentiellement sujettes aux inondations de cave", "FORTE"),
    "remnappe_inondation_cave_moyenne": ("Zones potentiellement sujettes aux inondations de cave", "MOYENNE"),
    "remnappe_inondation_cave_faible": ("Zones potentiellement sujettes aux inondations de cave", "FAIBLE"),
    "remnappe_inondation_cave_inconnue": ("Zones potentiellement sujettes aux inondations de cave", None),
    "remnappe_aucun_risque_forte": ("Pas de débordement de nappe ni d'inondation de cave", "FORTE"),
    "remnappe_aucun_risque_moyenne": ("Pas de débordement de nappe ni d'inondation de cave", "MOYENNE"),
    "remnappe_aucun_risque_faible": ("Pas de débordement de nappe ni d'inondation de cave", "FAIBLE"),
    "remnappe_aucun_risque_inconnue": ("Pas de débordement de nappe ni d'inondation de cave", None),
}


REGLES_WFS: Dict[str, tuple] = {
    "alea_debordement_frequent": ("alea_debordement", "01FOR"),
    "alea_debordement_moyen": ("alea_debordement", "02MOY"),
    "alea_debordement_rare": ("alea_debordement", "04FAI"),
    "alea_ruissellement_frequent": ("alea_ruissellement", "01FOR"),
    "alea_ruissellement_moyen": ("alea_ruissellement", "02MOY"),
    "alea_ruissellement_rare": ("alea_ruissellement", "04FAI"),
    "alea_submersion_frequent": ("alea_submersion", "01FOR"),
    "alea_submersion_moyen": ("alea_submersion", "02MOY"),
    "alea_submersion_moyen_cc": ("alea_submersion", "03MCC"),
    "alea_submersion_rare": ("alea_submersion", "04FAI"),
    "territoire_risque_important_inondation": ("territoire_risque_important", None),
    "ouvrage_protection_inondation": ("ouvrage_protection", None),
    "zone_sur_alea_inondation": ("zone_sur_alea", None),
    "zone_soustraite_alea_inondation": ("zone_soustraite_alea", None),
}
