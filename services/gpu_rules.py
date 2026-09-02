"""Résolution du bloc H→HV (fiche d'information détaillée GPU + SUP).

Contrairement au bloc Géorisques (`georisques_rules.py`, table figée de
rôles connus à l'avance), les rôles pertinents pour CE fichier précis
sont déterminés à partir du `ColumnLayout` déjà résolu — une colonne
absente de ce fichier particulier n'a simplement aucune entrée (pas de
"N" inutile pour un rôle sans colonne, jamais un role_code deviné).
Voir `services/gpu_mappings.py` pour la table icône->catégorie `du`, et
`services/excel_service.py::bootstrap_from_template` pour l'attribution
des `role_code` `gpu_du_*`/`gpu_sup_*`."""

from __future__ import annotations

from typing import Dict, Optional, Set, Tuple

from models.colonne import ColumnLayout
from models.parcelle import Parcelle
from services.urbanisme_service import UrbanismeService

_TYPENAME_DU = "info_lin,info_pct,info_surf,prescription_lin,prescription_pct,prescription_surf"
_TYPENAME_SUP = "assiette_sup_l,assiette_sup_s,assiette_sup_p"


def _role_vers_code_du(role: str) -> Optional[Tuple[str, str]]:
    """`"gpu_du_prescription_05-00"` -> `("prescription", "05-00")` —
    analyse directement la CHAÎNE du role_code plutôt qu'une table
    inverse construite depuis `DU_MAPPING` (indexé par icône) : un rôle
    peut être atteint soit par icône (via `DU_MAPPING`), soit par alias
    texte (voir `config.ROLES_CANONIQUES_VALIDES` — nécessaire pour les
    colonnes dont l'icône a été perdue dans un fichier réel donné, ex.
    `Didi-Arbent.xlsx` par rapport au gabarit officiel) ; les deux
    chemins doivent produire le même `(type, code)` sans dépendre de
    l'un ou l'autre en particulier."""
    if not role.startswith("gpu_du_"):
        return None
    reste = role[len("gpu_du_"):]
    type_, _, code = reste.partition("_")
    if not type_ or not code:
        return None
    return type_, code


def _code_du_depuis_feature(feature: dict) -> Optional[Tuple[str, str]]:
    """`(famille, code)` d'une feature `info_*`/`prescription_*` —
    famille déduite du préfixe de l'`id` (ex: `"prescription_surf.123"`
    -> `"prescription"`), code assemblé depuis `typepsc`+`stypepsc`
    (confirmé en direct : `"05"` + `"00"` -> `"05-00"`, seule
    combinaison de champs qui donne le code complet — `typepsc` seul ne
    donne que la famille à 2 chiffres). Renvoie `None` si les champs
    nécessaires sont absents (jamais deviné)."""
    feature_id = feature.get("id", "")
    prefixe = feature_id.split(".")[0] if "." in feature_id else ""
    if prefixe.startswith("prescription"):
        famille = "prescription"
    elif prefixe.startswith("info"):
        famille = "information"
    else:
        return None
    props = feature.get("properties", {})
    type_ = props.get("typepsc") or props.get("typeinf")
    stype = props.get("stypepsc") or props.get("stypeinf")
    if not type_ or stype is None:
        return None
    return famille, f"{type_}-{stype}"


def resoudre_gpu_detaille(
    parcelle: Parcelle, urbanisme: UrbanismeService, layout: ColumnLayout,
) -> Dict[str, str]:
    """Renvoie `{role_code: "O"/"N"}` pour tous les rôles
    `gpu_du_*`/`gpu_sup_*` RÉELLEMENT présents dans `layout` (ce
    fichier précis) — jamais une liste figée."""
    roles_du = {r for r in layout.par_role if r.startswith("gpu_du_")}
    roles_sup = {r for r in layout.par_role if r.startswith("gpu_sup_")}
    if not roles_du and not roles_sup:
        return {}

    dep, code_com = parcelle.code_insee[:2], parcelle.code_insee[2:]
    parcel_id = urbanisme.build_parcel_id(dep, code_com, "000", "000", parcelle.section, parcelle.numero)

    valeurs: Dict[str, str] = {}

    if roles_du:
        features = urbanisme.get_feature_info("du", _TYPENAME_DU, parcel_id)
        features = urbanisme.dedup_par_version_recente(features)
        codes_trouves: Set[Tuple[str, str]] = set()
        for f in features:
            code = _code_du_depuis_feature(f)
            if code:
                codes_trouves.add(code)
        for role in roles_du:
            code_attendu = _role_vers_code_du(role)
            if code_attendu is None:
                continue  # role_code gpu_du_* inconnu de DU_MAPPING (ne devrait pas arriver)
            valeurs[role] = "O" if code_attendu in codes_trouves else "N"

    if roles_sup:
        features_sup = urbanisme.get_feature_info("sup", _TYPENAME_SUP, parcel_id)
        codes_sup_trouves = {
            (f.get("properties", {}).get("suptype") or "").upper() for f in features_sup
        }
        for role in roles_sup:
            code_attendu = role[len("gpu_sup_"):].upper()
            valeurs[role] = "O" if code_attendu in codes_sup_trouves else "N"

    return valeurs


_ROLES_SCOT = {
    "schema_coherence_territoriale_publie",
    "schema_coherence_territoriale_non_publie",
    "perimetre_scot_arrete",
}


def resoudre_scot(parcelle: Parcelle, urbanisme: UrbanismeService, layout: ColumnLayout) -> Dict[str, str]:
    """SCOT (Schéma de Cohérence Territoriale) — catégorie GPU séparée
    de `du`/`sup` (voir `services/gpu_mappings.py::ROLES_PERSONNALISES_
    PAR_ICONE`), pas de liste de codes officielle (`/standard/scot-
    categories` confirmé 404 en direct). `feature-info/scot` (sans
    `typeName`, confirmé nécessaire — voir `UrbanismeService.
    get_feature_info`) renvoie directement le SCOT couvrant la parcelle,
    avec un champ `approved` (booléen).

    CONFIRMÉ en direct (Arboys en Bugey) : `{"name": "scot_200040350",
    "title": "SCOT BUGEY", "approved": true}` — donc "publié" = existe
    ET approuvé. "non publié" (l'opposé, existe mais PAS encore
    approuvé) et "arrêté" (existence du périmètre, peu importe le statut
    d'approbation) sont STRUCTURELS : lecture directe du sens des termes
    français, jamais rencontré de parcelle réelle avec `approved: false`
    pour confirmer empiriquement ces deux-là."""
    roles_scot = {r for r in layout.par_role if r in _ROLES_SCOT}
    if not roles_scot:
        return {}

    dep, code_com = parcelle.code_insee[:2], parcelle.code_insee[2:]
    parcel_id = urbanisme.build_parcel_id(dep, code_com, "000", "000", parcelle.section, parcelle.numero)
    features = urbanisme.get_feature_info("scot", None, parcel_id)
    existe = bool(features)
    approuve = any(f.get("properties", {}).get("approved") for f in features)

    valeurs: Dict[str, str] = {}
    if "schema_coherence_territoriale_publie" in roles_scot:
        valeurs["schema_coherence_territoriale_publie"] = "O" if (existe and approuve) else "N"
    if "schema_coherence_territoriale_non_publie" in roles_scot:
        valeurs["schema_coherence_territoriale_non_publie"] = "O" if (existe and not approuve) else "N"
    if "perimetre_scot_arrete" in roles_scot:
        valeurs["perimetre_scot_arrete"] = "O" if existe else "N"
    return valeurs


def resoudre_secteur_cc(parcelle: Parcelle, urbanisme: UrbanismeService, layout: ColumnLayout) -> Dict[str, str]:
    """"Secteur réservé aux activités" — sectorisation propre aux
    communes en CARTE COMMUNALE (pas de PLU), `typeName=secteur_cc`.
    CONFIRMÉ en direct (commune de Bézéril, 32051, réellement en carte
    communale au 2025-07-15) : la liste officielle des 4 types de secteur
    de carte communale (`/standard/du-categories`, type="secteur") donne
    exactement `{"01": "Secteur ouvert à la construction", "02":
    "Secteur réservé aux activités", "03": "Secteur non ouvert à la
    construction...", "99": "Zone non couverte"}`, et le champ réel
    `typesect` d'une feature `secteur_cc` correspond exactement à ce
    code ("03" confirmé en direct sur une vraie parcelle de Bézéril,
    libelong identique au libellé officiel).

    Pour une commune SANS carte communale (PLU/PLUi, comme Arboys en
    Bugey), `secteur_cc` renvoie simplement 0 feature — "N" est alors la
    réponse VRAIE (ce mécanisme de zonage ne s'applique pas ici), pas une
    valeur par défaut devinée.

    Étendu (2026-08-24) aux 2 autres valeurs du MÊME enum officiel à 4
    valeurs déjà récupéré pour "02" (pas une nouvelle investigation) :
    "01" ("Secteur ouvert à la construction", rôle
    `secteur_ouvert_construction`) et "03" ("Secteur non ouvert à la
    construction...", rôle `secteur_non_ouvert_construction` — en-tête du
    gabarit "Constructions non autorisées", même concept)."""
    roles_secteur_cc = {
        "01": "secteur_ouvert_construction",
        "02": "secteur_reserve_activites",
        "03": "secteur_non_ouvert_construction",
    }
    roles_presents = {code: role for code, role in roles_secteur_cc.items() if role in layout.par_role}
    if not roles_presents:
        return {}
    dep, code_com = parcelle.code_insee[:2], parcelle.code_insee[2:]
    parcel_id = urbanisme.build_parcel_id(dep, code_com, "000", "000", parcelle.section, parcelle.numero)
    features = urbanisme.get_feature_info("du", "secteur_cc", parcel_id)
    codes_trouves = {f.get("properties", {}).get("typesect") for f in features}
    return {role: ("O" if code in codes_trouves else "N") for code, role in roles_presents.items()}


def resoudre_zone_humide_ou_littoral(
    parcelle: Parcelle, urbanisme: UrbanismeService, layout: ColumnLayout,
) -> Dict[str, str]:
    """"Zone Humide / Espaces remarquables du littoral" — l'en-tête
    combine explicitement 2 codes officiels DISTINCTS (confirmé en
    direct dans `/standard/du-categories`) : `prescription|31-00`
    ("Espaces remarquables du littoral") et `prescription|31-05`
    ("Marais, vasières, tourbières, plans d'eau, les zones humides et
    milieux temporairement immergés") — répond "O" si L'UN DES DEUX
    s'applique (union, pas un seul choisi au hasard). Voir
    `services/gpu_mappings.py::ROLES_PERSONNALISES_PAR_ICONE` pour le
    rattachement de l'icône à ce rôle."""
    if "zone_humide_ou_littoral" not in layout.par_role:
        return {}
    dep, code_com = parcelle.code_insee[:2], parcelle.code_insee[2:]
    parcel_id = urbanisme.build_parcel_id(dep, code_com, "000", "000", parcelle.section, parcelle.numero)
    features = urbanisme.get_feature_info("du", _TYPENAME_DU, parcel_id)
    codes_trouves = {c for f in features if (c := _code_du_depuis_feature(f))}
    correspond = ("prescription", "31-00") in codes_trouves or ("prescription", "31-05") in codes_trouves
    return {"zone_humide_ou_littoral": "O" if correspond else "N"}


def resoudre_zone_urbaine_patrimoniale(
    parcelle: Parcelle, urbanisme: UrbanismeService, layout: ColumnLayout,
) -> Dict[str, str]:
    """"Zone urbaine Patrimoniale" — AUCUN code officiel dédié trouvé
    (ni dans `/standard/du-categories`, ni comme sous-type de `typezone`
    "U" — seules les valeurs U/A/N/AU rencontrées en investigation live).
    STRUCTUREL, jamais confirmé contre un vrai "O" : hypothèse raisonnée
    que la colonne combine "Zone urbaine" (typezone == "U") ET la
    présence d'un overlay "Site patrimonial remarquable"
    (`information|01-00`, le SEUL overlay patrimoine générique officiel,
    déjà utilisé ailleurs dans ce projet — `gpu_du_information_01-01`
    "Secteur sauvegardé" est plus spécifique, PSMV) sur la même parcelle
    — pas un code inventé, une COMBINAISON logique de 2 signaux déjà
    fiables. À corriger dès qu'un vrai exemple positif est rencontré."""
    if "zone_urbaine_patrimoniale" not in layout.par_role:
        return {}
    # Polygone complet, pas le centroïde seul — même correctif que
    # `resoudre_zonage` (main.py, 2026-09-02) : une parcelle à cheval
    # sur une zone U et une zone non-U ne doit pas dépendre de la seule
    # position du centroïde pour être considérée "urbaine".
    features_zonage = urbanisme.get_zone_urba(parcelle.geometry)
    features_zonage = urbanisme.dedup_par_version_recente(features_zonage)
    est_urbaine = any(f["properties"].get("typezone") == "U" for f in features_zonage)
    if not est_urbaine:
        return {"zone_urbaine_patrimoniale": "N"}
    dep, code_com = parcelle.code_insee[:2], parcelle.code_insee[2:]
    parcel_id = urbanisme.build_parcel_id(dep, code_com, "000", "000", parcelle.section, parcelle.numero)
    features_du = urbanisme.get_feature_info("du", _TYPENAME_DU, parcel_id)
    codes_trouves = {c for f in features_du if (c := _code_du_depuis_feature(f))}
    est_patrimoniale = ("information", "01-00") in codes_trouves
    return {"zone_urbaine_patrimoniale": "O" if est_patrimoniale else "N"}
