"""Résolution d'identité de colonne — le cœur de ce projet, sans
équivalent côté wallon (voir le plan : `COLUMN_RULES` là-bas suppose des
lettres de colonne fixes, ce qui n'est pas vrai ici puisque les en-têtes
dérivent d'un fichier à l'autre).

Algorithme en couches, jamais de devinette silencieuse (voir
`resolve_column`) :
    1. Icône (hash exact connu) — signal le plus fiable, prioritaire
       sur le texte pour les colonnes qui en ont une (bloc H→HV).
    2. Code normalisé (SENSIBLE à la casse depuis le 2026-08-21 — voir
       `utils.text_normalize.normaliser_code_zone` : "Ua" et "UA" sont
       des zones réellement différentes, jamais fusionnées) — pour le
       bloc de zonage.
    3. Alias texte déjà promu manuellement par un humain (texte libre,
       toujours insensible à la casse, voir `normaliser`).
    4. Correspondance floue texte — SUGGESTION SEULEMENT, jamais
       appliquée, journalisée pour revue humaine dans le GUI.
    5. Non résolu — laissé vide, journalisé avec tout le contexte utile
       (commune, rue, lettre de colonne) pour relais manuel.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import config
from models.colonne import ColumnResolution, MethodeResolution
from utils.logger import get_logger
from utils.text_normalize import meilleure_correspondance, normaliser, normaliser_code_zone

_logger = get_logger("services.column_registry_service")

# Seuil de score (0..1) à partir duquel une correspondance floue devient
# une suggestion journalisée — en dessous, journalisée quand même (pour
# audit) mais sans même valoir la peine d'être montrée en priorité dans
# le GUI. Choisi arbitrairement à ce stade (aucune donnée réelle ne
# permet encore de calibrer plus finement) ; à ajuster une fois le GUI
# de registre en usage réel.
SEUIL_SUGGESTION_FLOUE = 0.85


class ColumnRegistryService:
    def __init__(self, registry_dir: Path) -> None:
        registry_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = registry_dir / "column_registry.sqlite3"
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=30)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS icon_registry (
                    icon_hash TEXT PRIMARY KEY,
                    role_code TEXT,
                    role_label TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    sample_png BLOB,
                    first_seen_commune TEXT,
                    first_seen_rue TEXT,
                    first_seen_column_letter TEXT,
                    first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS code_registry (
                    normalized_code TEXT PRIMARY KEY,
                    role_code TEXT NOT NULL,
                    canonical_label TEXT,
                    color_family_id TEXT,
                    status TEXT NOT NULL DEFAULT 'known',
                    last_seen_column_letter TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS text_alias (
                    normalized_text TEXT PRIMARY KEY,
                    role_code TEXT NOT NULL,
                    promoted_by TEXT,
                    promoted_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS text_fuzzy_suggestion_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    observed_text TEXT,
                    best_candidate_role_code TEXT,
                    score REAL,
                    commune TEXT,
                    rue TEXT,
                    file_path TEXT,
                    status TEXT DEFAULT 'suggested',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS column_layout_snapshot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    file_path TEXT,
                    commune TEXT,
                    rue TEXT,
                    column_letter TEXT,
                    header_text TEXT,
                    icon_hash TEXT,
                    normalized_code TEXT,
                    resolved_role_code TEXT,
                    resolution_method TEXT,
                    confidence REAL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    # -- résolution ---------------------------------------------------

    def resolve_column(
        self,
        column_letter: str,
        header_text: str,
        icon_hash: Optional[str] = None,
        code_candidate: Optional[str] = None,
        fuzzy_candidates: Optional[List[Tuple[str, str]]] = None,
        *,
        run_id: str = "",
        file_path: str = "",
        commune: str = "",
        rue: str = "",
    ) -> ColumnResolution:
        """Résout UNE colonne en couches (voir docstring de module).

        `code_candidate` : le code déjà extrait de l'en-tête par
        l'appelant (ex: le texte de l'en-tête lui-même pour une colonne
        du bloc de zonage) — cette méthode ne décide jamais elle-même
        SI une colonne est "une colonne à code", c'est à `ExcelService`
        (qui connaît la structure du fichier) de le déterminer et de ne
        passer `code_candidate` que pour les colonnes concernées.

        `fuzzy_candidates` : liste de `(role_code, libelle_canonique)`
        à essayer en dernier recours — typiquement la liste officielle
        `du-categories` pour le bloc GPU, vide/`None` pour les blocs
        sans référentiel connu.

        Chaque appel journalise systématiquement le résultat dans
        `column_layout_snapshot`, résolu ou non — c'est le mécanisme
        concret de log demandé (lettre de colonne + code/famille
        matché + contexte commune/rue)."""
        resolution = self._resolve_layers(
            column_letter, header_text, icon_hash, code_candidate, fuzzy_candidates,
            commune=commune, rue=rue, file_path=file_path,
        )
        self._log_snapshot(run_id, file_path, commune, rue, resolution, code_candidate)
        return resolution

    def _resolve_layers(
        self,
        column_letter: str,
        header_text: str,
        icon_hash: Optional[str],
        code_candidate: Optional[str],
        fuzzy_candidates: Optional[List[Tuple[str, str]]],
        *,
        commune: str,
        rue: str,
        file_path: str,
    ) -> ColumnResolution:
        # Couche 1 : icône CONNUE — prioritaire, jamais de repli sur le
        # texte pour une colonne dont l'icône est déjà approuvée (voir
        # le plan : l'icône est strictement plus fiable une fois connue,
        # GE/GG en sont la preuve concrète). Une icône INCONNUE, en
        # revanche, ne bloque plus les couches suivantes — corrigé après
        # avoir trouvé un vrai contre-exemple (bloc SUP du gabarit
        # officiel) : plusieurs colonnes réellement différentes (ex.
        # "Canalisation électrique-I4" / "...chaleur-I9") partagent la
        # MÊME icône générique dans le gabarit lui-même (pas un artefact
        # de dérive entre fichiers, une ambiguïté du gabarit lui-même) —
        # refuser tout repli aurait rendu ces colonnes ÉTERNELLEMENT non
        # résolues alors que leur code (couche 2) suffit à les
        # distinguer sans ambiguïté.
        if icon_hash:
            connu = self._icon_role(icon_hash)
            if connu is not None:
                role_code, role_label = connu
                self._toucher_icone(icon_hash, commune, rue, column_letter)
                return ColumnResolution(
                    column_letter=column_letter, header_text=header_text,
                    role_code=role_code, method=MethodeResolution.ICONE,
                    confidence=1.0, icon_hash=icon_hash,
                )
            self._enregistrer_icone_pending(icon_hash, header_text, commune, rue, column_letter)
            # Pas de retour ici : on tente les couches suivantes plutôt
            # que d'abandonner immédiatement (voir commentaire ci-dessus).

        # Couche 2 : code normalisé (sensible à la casse, insensible aux
        # accents/espaces parasites — voir normaliser_code_zone)
        if code_candidate:
            norm = normaliser_code_zone(code_candidate)
            role_code = self._code_role(norm)
            if role_code is not None:
                self._toucher_code(norm, column_letter)
                return ColumnResolution(
                    column_letter=column_letter, header_text=header_text,
                    role_code=role_code, method=MethodeResolution.CODE,
                    confidence=1.0, normalized_code=norm,
                )

        # Couche 3 : alias texte déjà promu manuellement
        norm_texte = normaliser(header_text)
        alias_role = self._alias_role(norm_texte)
        if alias_role is not None:
            return ColumnResolution(
                column_letter=column_letter, header_text=header_text,
                role_code=alias_role, method=MethodeResolution.ALIAS,
                confidence=1.0, normalized_code=code_candidate and normaliser_code_zone(code_candidate),
            )

        # Couche 4 : suggestion floue — jamais appliquée
        if fuzzy_candidates:
            meilleur = meilleure_correspondance(header_text, fuzzy_candidates)
            if meilleur is not None:
                role_code, libelle, score = meilleur
                self._journaliser_suggestion(header_text, role_code, score, commune, rue, file_path)
                return ColumnResolution(
                    column_letter=column_letter, header_text=header_text,
                    role_code=None, method=MethodeResolution.SUGGESTION_FLOUE,
                    confidence=score,
                )

        # Couche 5 : non résolu
        return ColumnResolution(
            column_letter=column_letter, header_text=header_text,
            role_code=None, method=MethodeResolution.NON_RESOLU, confidence=0.0,
        )

    def _log_snapshot(
        self, run_id: str, file_path: str, commune: str, rue: str,
        resolution: ColumnResolution, code_candidate: Optional[str],
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO column_layout_snapshot "
                "(run_id, file_path, commune, rue, column_letter, header_text, icon_hash, "
                "normalized_code, resolved_role_code, resolution_method, confidence) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, file_path, commune, rue, resolution.column_letter,
                    resolution.header_text, resolution.icon_hash,
                    normaliser_code_zone(code_candidate) if code_candidate else None,
                    resolution.role_code, resolution.method.value, resolution.confidence,
                ),
            )
            conn.commit()

    # -- icônes ---------------------------------------------------------

    def _icon_role(self, icon_hash: str) -> Optional[Tuple[str, str]]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT role_code, role_label FROM icon_registry WHERE icon_hash = ? AND status = 'known'",
                (icon_hash,),
            ).fetchone()
        return (row[0], row[1]) if row and row[0] else None

    def _enregistrer_icone_pending(
        self, icon_hash: str, header_text: str, commune: str, rue: str, column_letter: str,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO icon_registry "
                "(icon_hash, status, first_seen_commune, first_seen_rue, first_seen_column_letter) "
                "VALUES (?, 'pending', ?, ?, ?)",
                (icon_hash, commune, rue, column_letter),
            )
            conn.execute(
                "UPDATE icon_registry SET last_seen_at = CURRENT_TIMESTAMP WHERE icon_hash = ?",
                (icon_hash,),
            )
            conn.commit()
        _logger.warning(
            "Icône inconnue (hash=%s) colonne %s ('%s'), commune=%s rue=%s — en attente de classification.",
            icon_hash[:12], column_letter, header_text, commune, rue,
        )

    def _toucher_icone(self, icon_hash: str, commune: str, rue: str, column_letter: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE icon_registry SET last_seen_at = CURRENT_TIMESTAMP WHERE icon_hash = ?",
                (icon_hash,),
            )
            conn.commit()

    def enregistrer_icone_avec_image(
        self, icon_hash: str, png_bytes: bytes, commune: str, rue: str, column_letter: str,
    ) -> None:
        """Enregistre une icône inconnue avec sa miniature (BLOB) — à
        appeler par ExcelService en plus de `resolve_column` (qui ne
        reçoit pas les octets PNG, seulement le hash) pour que le GUI de
        registre puisse l'afficher. Ne modifie jamais `status` si
        l'icône est déjà connue."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO icon_registry "
                "(icon_hash, status, sample_png, first_seen_commune, first_seen_rue, first_seen_column_letter) "
                "VALUES (?, 'pending', ?, ?, ?, ?)",
                (icon_hash, png_bytes, commune, rue, column_letter),
            )
            conn.execute(
                "UPDATE icon_registry SET sample_png = COALESCE(sample_png, ?) WHERE icon_hash = ?",
                (png_bytes, icon_hash),
            )
            conn.commit()

    def approuver_icone(self, icon_hash: str, role_code: str, role_label: str) -> None:
        """Approbation humaine (GUI) — seule voie légitime pour faire
        passer une icône de `pending` à `known`."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE icon_registry SET role_code = ?, role_label = ?, status = 'known' "
                "WHERE icon_hash = ?",
                (role_code, role_label, icon_hash),
            )
            conn.commit()

    def icones_en_attente(self) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT icon_hash, sample_png, first_seen_commune, first_seen_rue, "
                "first_seen_column_letter FROM icon_registry WHERE status = 'pending'"
            ).fetchall()
        return [
            {
                "icon_hash": h, "sample_png": png, "first_seen_commune": c,
                "first_seen_rue": r, "first_seen_column_letter": col,
            }
            for h, png, c, r, col in rows
        ]

    # -- codes ------------------------------------------------------

    def code_connu(self, code_brut: str) -> bool:
        """True si ce code (normalisé, SENSIBLE à la casse — voir
        `normaliser_code_zone`) est déjà enregistré `known` — utilisé
        par la Phase A (`excel_service.ensure_columns_for_codes`,
        `main.py::decouvrir_codes_zone_manquants`) pour ne considérer
        que les codes VRAIMENT nouveaux, jamais recréer une colonne déjà
        gérée."""
        return self._code_role(normaliser_code_zone(code_brut)) is not None

    def _code_role(self, normalized_code: str) -> Optional[str]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT role_code FROM code_registry WHERE normalized_code = ? AND status = 'known'",
                (normalized_code,),
            ).fetchone()
        return row[0] if row else None

    def _toucher_code(self, normalized_code: str, column_letter: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE code_registry SET last_seen_column_letter = ? WHERE normalized_code = ?",
                (column_letter, normalized_code),
            )
            conn.commit()

    def enregistrer_code(
        self, code_brut: str, role_code: str, canonical_label: str,
        color_family_id: Optional[str] = None, status: str = "known",
    ) -> None:
        """Enregistre un code de zonage connu (ex: lors du scan initial
        du gabarit, où chaque colonne du bloc KL→RR est déjà un code
        connu par construction, ou lors de la création d'une nouvelle
        colonne — voir `ensure_columns_for_codes` côté ExcelService).
        SENSIBLE à la casse (voir `normaliser_code_zone`)."""
        norm = normaliser_code_zone(code_brut)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO code_registry "
                "(normalized_code, role_code, canonical_label, color_family_id, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (norm, role_code, canonical_label, color_family_id, status),
            )
            conn.commit()

    # -- alias texte (promotion manuelle depuis une suggestion floue) --

    def _alias_role(self, normalized_text: str) -> Optional[str]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT role_code FROM text_alias WHERE normalized_text = ?",
                (normalized_text,),
            ).fetchone()
        return row[0] if row else None

    def promouvoir_alias(self, header_text: str, role_code: str, promoted_by: str = "") -> None:
        """Promotion manuelle (GUI) d'un texte observé en alias durable
        — après ça, ce texte exact résout automatiquement sans repasser
        par la correspondance floue à chaque run."""
        norm = normaliser(header_text)
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO text_alias (normalized_text, role_code, promoted_by) "
                "VALUES (?, ?, ?)",
                (norm, role_code, promoted_by),
            )
            conn.commit()

    def seed_roles_canoniques(self, roles: Dict[str, List[str]], promoted_by: str = "canonique") -> None:
        """Amorce le registre depuis `config.ROLES_CANONIQUES_VALIDES` —
        voir le plan : contrairement aux icônes/codes, ces colonnes
        n'ont pas d'identité fiable dérivable d'UN fichier (ni icône, ni
        couleur de famille), donc leur `role_code` est choisi par nous
        une fois pour toutes, jamais dérivé du texte d'un fichier
        d'amorçage précis. Idempotent (`INSERT OR REPLACE`), peut être
        rappelé à chaque run sans effet si rien n'a changé."""
        for role_code, libelles in roles.items():
            for libelle in libelles:
                self.promouvoir_alias(libelle, role_code, promoted_by=promoted_by)

    def _journaliser_suggestion(
        self, observed_text: str, role_code: str, score: float, commune: str, rue: str, file_path: str,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO text_fuzzy_suggestion_log "
                "(observed_text, best_candidate_role_code, score, commune, rue, file_path) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (observed_text, role_code, score, commune, rue, file_path),
            )
            conn.commit()
        if score >= SEUIL_SUGGESTION_FLOUE:
            _logger.warning(
                "Suggestion floue (score=%.2f) pour '%s' -> rôle candidat '%s' — jamais appliquée, "
                "à valider dans le registre de colonnes.", score, observed_text, role_code,
            )

    def marquer_suggestion_traitee(self, suggestion_id: int, status: str = "promu") -> None:
        """Marque une ligne de `text_fuzzy_suggestion_log` comme traitée
        (`status != 'suggested'`) — sans ça, une suggestion déjà promue
        en alias continuerait à réapparaître indéfiniment dans le GUI à
        chaque nouveau run (bug réel trouvé en testant le GUI : promouvoir
        un alias n'a aucun effet sur cette table, qui est une source
        DISTINCTE de `text_alias`)."""
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE text_fuzzy_suggestion_log SET status = ? WHERE id = ?",
                (status, suggestion_id),
            )
            conn.commit()

    def suggestions_en_attente(self, seuil: float = SEUIL_SUGGESTION_FLOUE) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, observed_text, best_candidate_role_code, score, commune, rue "
                "FROM text_fuzzy_suggestion_log WHERE status = 'suggested' AND score >= ? "
                "ORDER BY score DESC",
                (seuil,),
            ).fetchall()
        return [
            {"id": i, "observed_text": t, "role_code": r, "score": s, "commune": c, "rue": rue}
            for i, t, r, s, c, rue in rows
        ]

    def colonnes_non_resolues_recentes(self, limite: int = 200) -> List[Dict[str, Any]]:
        """Colonnes texte non résolues (`resolution_method = 'non_resolu'`,
        pas d'icône) sans même une suggestion floue à promouvoir — le
        troisième cas du GUI de registre, à côté des icônes en attente et
        des suggestions : une colonne totalement inconnue (aucun
        `fuzzy_candidates` fourni pour son bloc, ou aucun candidat au-dessus
        du seuil) doit quand même pouvoir être assignée à la main, pas
        seulement journalisée sans recours (voir le plan/discussion :
        interface conviviale pour insérer soi-même un rôle manquant).
        Dédupliqué par texte d'en-tête (la même colonne peut apparaître
        dans plusieurs runs), la plus récente occurrence gardée."""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT header_text, column_letter, commune, rue, file_path, MAX(created_at)
                FROM column_layout_snapshot
                WHERE resolution_method = 'non_resolu' AND (icon_hash IS NULL OR icon_hash = '')
                GROUP BY header_text
                ORDER BY MAX(created_at) DESC
                """
            ).fetchall()
        resultat = []
        for h, c, commune, rue, f, _ in rows:
            # Exclu si un alias a été créé depuis ce scan (la ligne
            # 'non_resolu' reste dans l'historique, mais la colonne est
            # maintenant résolue pour de vrai — ne plus la proposer).
            if self._alias_role(normaliser(h)) is not None:
                continue
            resultat.append({"header_text": h, "column_letter": c, "commune": commune, "rue": rue, "file_path": f})
            if len(resultat) >= limite:
                break
        return resultat

    # -- familles de couleur ------------------------------------------

    def classer_famille_couleur(self, rgb: Optional[str]) -> Optional[str]:
        """Détermine à quelle famille de couleur (des 6 ancres, voir
        `config.COLOR_FAMILY_ANCHORS`) un RGB donné correspond, par
        correspondance EXACTE — confirmé en investigation live : les
        189 colonnes du bloc KL→RR matchent chacune exactement l'une
        des 6 couleurs d'ancre, 0 non matchée sur le vrai gabarit.
        Renvoie `None` sans deviner si le RGB ne matche aucune ancre
        connue (une nouvelle famille de couleur serait un événement
        structurel majeur du gabarit, à traiter manuellement, jamais
        supposé automatiquement)."""
        if not rgb:
            return None
        for family_id, anchor_rgb in config.COLOR_FAMILY_ANCHORS.items():
            if rgb == anchor_rgb:
                return family_id
        return None
