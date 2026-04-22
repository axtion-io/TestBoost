# TODO

## Bugs / incohérences

- [ ] **`max_correction_retries` dans `config.yaml` n'est pas lu.**
  Le champ est écrit par défaut dans `config.yaml` via [session_tracker.py:71](src/lib/session_tracker.py#L71),
  mais la vraie limite de tentatives est la constante hardcodée
  `_MAX_COMPILE_FIX_ATTEMPTS = 3` dans [cli.py:643](src/lib/cli.py#L643).
  Conséquence : éditer `config.yaml` pour pousser à 5 tentatives n'a aucun effet.
  Fix attendu : lire `max_correction_retries` depuis `config.yaml` et l'injecter dans
  `_attempt_compile_fix` (et `_attempt_test_runtime_fix`). Si le champ n'est pas
  dans config.yaml, retomber sur la valeur par défaut.

## Features incomplètes

- [ ] **Slash commands manquantes pour `mutate` et `killer`.**
  Les commandes CLI existent (`python -m testboost mutate/killer`), les scripts
  wrapper dev `scripts/tb-mutate.{sh,ps1}` et `scripts/tb-killer.{sh,ps1}` existent,
  mais il n'y a pas de template dans `templates/commands/` et la liste `steps`
  de l'installer ([installer.py:86](src/lib/installer.py#L86)) ne les inclut pas.
  Conséquence : `python -m testboost install` ne déploie pas `testboost.mutate.md`
  ni `testboost.killer.md` côté projet cible.
  Fix attendu : créer les 2 templates `.md` (calqués sur `testboost.validate.md`)
  et ajouter `"mutate"` et `"killer"` dans `steps`.
