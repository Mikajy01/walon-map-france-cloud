# walon-map-france-cloud

Traitement automatique, dans le cloud (GitHub Actions), du livrable
cadastral/urbanisme français — copie autonome du pipeline de
[walon-map-france](../walon-map-france) (desktop), adaptée pour traiter
une **commune entière** au lieu de rues choisies à la main.

## Utilisation

Onglet **Actions** → workflow **"Traiter une commune"** → **Run
workflow**, avec :

- **commune**, **departement** (code `01` ou nom `Ain`, les deux
  marchent), **code_postal**
- **mode** :
  - `traiter_commune` (défaut) — découvre automatiquement toutes les
    rues de la commune et les traite.
  - `retenter_erreurs` — ne retente que les cellules d'inondation WFS
    Géorisques déjà en échec pour cette commune (voir
    `registry_data/cellules_a_revisiter.csv`), sans redécouverte.
- **traitement** :
  - `continuer` (défaut, sûr) — reprend le fichier d'état existant de
    cette commune (`state/{code_insee}_{commune}.xlsx`) là où il en
    était.
  - `nouveau` — **destructif** : réinitialise ce fichier depuis
    `templates/gabarit_officiel.xlsx` avant de traiter. Le registre de
    colonnes (icônes/codes déjà classifiés) n'est jamais touché par ce
    choix.

## Ce qui est commité automatiquement

Un job GitHub Actions est coupé à 6h. Le pipeline sauvegarde l'Excel
après **chaque parcelle traitée** (jamais seulement en fin de rue), et
s'arrête proprement, seul, environ 30 minutes avant cette limite (voir
`--budget-heures` dans `main.py`) — jamais tué en plein milieu d'une
sauvegarde. Le workflow commite ensuite l'état à jour (`state/`,
`registry_data/`), que le run soit fini ou non : un run incomplet est
signalé clairement (annotation GitHub + résumé dans les logs), et se
reprend simplement en relançant le workflow en `continuer`.

## Différences avec walon-map-france (desktop)

- Découverte automatique des rues d'une commune (`CommuneService.
  lister_voies`) au lieu d'une liste tapée à la main.
- Pas de GUI (headless, `main.py` en CLI uniquement).
- L'état (Excel de progression, registre de colonnes) est commité dans
  ce dépôt plutôt que géré localement par l'utilisateur — décision
  assumée : ce dépôt étant public, ces données le sont aussi.
