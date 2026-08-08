# Audit du projet ProBudget AI — 2026-08-08

Audit statique (lecture intégrale des `.py`) + tentative réelle d'exécution locale
(`pip install`, `streamlit run`). Environnement : Windows 10, Python 3.13.1, venv
jetable dédié (`.venv_audit/`, non commité, à supprimer après lecture de ce rapport).

---

## ⚠️ À traiter en priorité, indépendamment du reste

**La clé de compte de service Firebase actuellement utilisée doit être régénérée.**
Deux raisons distinctes et cumulatives :

1. **Historique git** : des fichiers de clé Firebase (`firebase_key.json`,
   `FIREBASE_SECRE.json`, `firebbase_key.json`) ont été committés puis supprimés à
   plusieurs reprises tôt dans l'historique de ce dépôt (dernière suppression au
   commit `99107f6`, "Fix: Utilisation des secrets Streamlit pour la connexion
   Firebase"). Ces blobs restent récupérables dans l'historique git tant qu'il n'est
   pas réécrit — même si le fichier n'existe plus dans le répertoire de travail actuel.
   Point rassurant : une recherche `git log -S` sur le `project_id` et le
   `private_key_id` actuellement présents dans `.streamlit/secrets.toml` ne trouve
   **aucune** occurrence dans tout l'historique, ce qui suggère fortement que la clé a
   déjà été régénérée après cette fuite initiale. Mais je n'ai pas pu confirmer à 100 %
   sans rouvrir les anciens blobs (ce que j'ai volontairement évité, voir point 2), et
   je ne sais pas si ce dépôt GitHub a été public ou forké à un moment donné.
2. **Incident survenu pendant cet audit** : pour inspecter la structure de
   `.streamlit/secrets.toml`, j'ai lancé une commande (`awk -F'='...`) qui a affiché
   **l'intégralité du fichier en clair dans ce transcript**, y compris la clé privée
   PEM complète. Ce n'était pas mon intention (je voulais juste lister les clés), mais
   le contenu a bel et bien été imprimé. Je n'ai pas réitéré l'erreur ensuite (la
   vérification de format a été refaite uniquement via `tomllib`, sans jamais
   réafficher le contenu), mais cette clé doit être considérée comme potentiellement
   exposée et régénérée dans la console Firebase (Paramètres du projet > Comptes de
   service > Générer une nouvelle clé privée), **puis remplacée dans
   `.streamlit/secrets.toml` et dans les secrets Streamlit Cloud**.

---

## Ce qui fonctionne (vérifié comment)

- **Le projet s'installe intégralement** : `pip install -r requirements.txt` dans un
  venv Python 3.13 propre réussit du premier coup, `prophet` inclus — sur Windows,
  `prophet` s'installe comme wheel précompilé (`prophet-1.3.0-py3-none-win_amd64.whl`),
  aucune compilation cmdstan nécessaire à l'installation. `import prophet` testé
  isolément : **OK**. La crainte initiale ("compilation cmdstan trop lourde") ne s'est
  pas concrétisée ici.
- **Le serveur démarre réellement** : `streamlit run app.py` lancé en arrière-plan,
  j'ai confirmé le serveur Uvicorn up (`Uvicorn server started on :::8765`), une vraie
  requête HTTP sur `/` renvoie **200 OK**, et aucune trace d'erreur ou de traceback
  serveur n'est apparue dans les logs pendant la fenêtre d'observation. Le serveur a
  été arrêté immédiatement après (processus tués, port 8765 vérifié libre) — je ne l'ai
  pas laissé tourner, d'autant qu'il s'était bindé sur une URL externe accessible
  depuis internet.
- **`python -m py_compile`** passe sans erreur sur tous les fichiers `.py` du dépôt.
- **`pyflakes`** (installé dans le venv d'audit) ne relève qu'un seul import mort sur
  l'ensemble du code (voir plus bas) — pas de variables inutilisées, pas d'erreurs de
  nom.
- **Plus aucun `€`/EUR codé en dur** : recherche exhaustive sur tous les `.py`. Les
  seules occurrences restantes sont légitimes : la table `CURRENCY_SYMBOLS` de
  `currency.py` (où `"EUR": "€"` est une donnée, pas un affichage figé) et le regex de
  `forms.py` (reconnaissance du mot-clé `eur` dans un ticket). Tous les affichages
  utilisateur (`app.py`, `utils.py`, `investments.py`, `plots.py`) passent bien par
  `base_currency`/`currency_symbol` dynamiques.
- **`.streamlit/secrets.toml` n'a jamais été commité** : confirmé par
  `git log --all -- .streamlit/secrets.toml` (vide) et `git check-ignore -v` (bien
  ignoré par la règle du `.gitignore`).
- **La détection de montant FCFA/EUR dans `forms.py`** (`extract_amount_from_text`) :
  relue en détail, la logique est cohérente (séparateur de recherche autour des
  mots-clés qui exclut désormais les retours à la ligne, distinction correcte
  espace-milliers vs virgule-décimale).
- **CI GitHub Actions** existe (`py_compile` + import individuel de 6 modules) et
  tourne sur chaque push vers `master`.

---

## Bugs trouvés, par gravité

### 🔴 Bloquant

**1. Collision d'identifiant Firestore entre deux comptes différents.**
`users.py` (et repris dans `app.py`, `investments.py`) dérive l'identifiant de
collection Firestore d'un utilisateur ainsi :
```python
st.session_state['uid'] = email.replace('.', '_').replace('@', '_at_')
```
Deux adresses email **valides et distinctes** peuvent produire le **même** uid. Exemple
concret : `jean.dupont@gmail.com` → `jean_dupont_at_gmail_com`, et
`jean_dupont@gmail.com` → `jean_dupont_at_gmail_com` (identique, car le point du nom
et le point du domaine sont tous deux remplacés par `_`). Les deux comptes liraient et
écriraient dans **les mêmes collections** `entries_<uid>` et `investments_<uid>` — deux
utilisateurs distincts partageraient silencieusement leurs transactions financières
privées (lecture ET écriture croisées), sans aucun message d'erreur. Ce n'est pas un
scénario exotique nécessitant une attaque : deux utilisateurs légitimes avec des emails
proches suffisent à le déclencher. Les documents `users/<email>` eux (login/mot de
passe) ne sont pas affectés — seule la donnée financière (`entries_*`,
`investments_*`) est concernée, car ces collections sont keyées sur le uid dérivé et
non sur l'email complet.
→ Correction recommandée : utiliser l'email complet en minuscule (ou un hash SHA-256
de l'email) comme identifiant de collection, jamais une transformation à collisions.

**2 & 3. Exposition de la clé Firebase** — voir la section "À traiter en priorité"
ci-dessus.

### 🟠 Important

**4. `.streamlit/secrets.toml` local n'est pas un TOML valide.** Le fichier contient un
objet JSON brut collé tel quel (`{ "type": "service_account", ... }`) au lieu du format
`[firebase]` + `clé = "valeur"` attendu par `secrets.toml.example`. Confirmé avec
`tomllib.load()` → `TOMLDecodeError: Invalid statement (at line 1, column 1)`. Ceci
bloque le test du flux "utilisateur connecté" en local (voir section suivante) — mais
n'affecte pas forcément le déploiement Streamlit Cloud, dont les secrets sont
généralement saisis via l'interface web dans un format différent. Point positif : même
avec ce fichier cassé, `app.py` ne plante pas brutalement, car le `try/except Exception`
générique autour de `DBClient()` dans `app.py` (ligne ~37) intercepte n'importe quelle
exception de chargement des secrets et affiche un message propre — ce n'est donc pas un
crash brut, juste un blocage pour qui veut tester en local avec ce fichier tel quel.

**5. `except ImportError` ne protège pas contre une vraie erreur dans `investments.py`.**
Dans `app.py` :
```python
try:
    from investments import investment_dashboard
    investment_dashboard(db, st.session_state['uid'], base_currency)
except ImportError:
    st.error("Le fichier 'investments.py' est manquant ou contient une erreur de syntaxe.")
```
Le commentaire/message annonce couvrir "une erreur de syntaxe", mais une `SyntaxError`
dans `investments.py` **n'est pas** une sous-classe d'`ImportError` en Python — elle ne
serait donc **pas interceptée** par ce `except`, et provoquerait un crash brut de la
page (traceback affiché tel quel) plutôt que le message propre annoncé. Idem pour
toute erreur d'exécution (`NameError`, `AttributeError`, etc.) qui surviendrait dans
`investment_dashboard()` lui-même.

**6. `get_entries()` (`temp_db_client.py`) n'a pas de filet de sécurité sur son
fallback.** Si la requête triée échoue, le code retente sans tri — mais si **cette
deuxième tentative échoue aussi** (ex. coupure réseau complète), l'exception n'est pas
interceptée et remonte jusqu'à `app.py`, qui ne l'attrape pas non plus autour de
`db.get_entries(...)` : la page plante avec un traceback brut au lieu d'un message
d'erreur propre. Même remarque pour `analysis.py::prepare_data()`, qui suppose que
chaque document a bien les clés `date`, `type`, `amount` — un document Firestore
incomplet ou corrompu (édition manuelle dans la console, ancien format) ferait planter
tout le tableau de bord avec un `KeyError` brut. Par contraste, `investments.py`
protège déjà ce cas précis (boucle qui complète les colonnes manquantes avec des
valeurs par défaut) — l'incohérence entre les deux fichiers illustre bien qu'il s'agit
d'un oubli plutôt que d'un choix délibéré.

**7. Fuite de détails d'exception bruts à l'utilisateur**, incohérente avec le reste du
code qui masque volontairement ces détails (commentaires explicites en ce sens dans
`users.py` et ailleurs) :
- `forms.py` ligne 102 : `st.sidebar.error(f"Erreur OCR : {e}")`
- `temp_db_client.py` ligne 100 : `st.error(f"Erreur d'ajout : {e}")`

Risque faible (pas de mot de passe en jeu ici) mais incohérent, et peut exposer des
détails d'implémentation (chemins internes, noms de champs Firestore).

**8. CI incomplète : `investments.py` n'est pas vérifié.**
`.github/scripts/check_imports.py` liste explicitement les modules à importer en CI
(`users`, `temp_db_client`, `currency`, `utils`, `analysis`, `forms`) mais **oublie
`investments.py`**, qui est justement importé dynamiquement (donc plus fragile) dans
`app.py`. Une régression dans ce fichier ne serait détectée par la CI que via
`py_compile` (erreurs de syntaxe uniquement), pas via un import réel — ce qui est
exactement le type de bug que ce script a été écrit pour attraper (cf. son
commentaire d'intention sur le bug passlib/Python).

**9. "Rester connecté" — un seul jeton actif par utilisateur.**
`_issue_remember_me_cookie()` écrase `remember_token_hash`/`remember_token_expires`
sur le document utilisateur à chaque connexion avec "rester connecté" coché. Se
connecter avec cette case cochée sur un **deuxième appareil** invalide silencieusement
le cookie du premier : au prochain chargement, celui-ci ne matchera plus le hash stocké
et l'utilisateur retombera sur l'écran de connexion, sans aucun message expliquant
pourquoi il a été déconnecté. Comportement surprenant pour quelqu'un qui utilise
l'app à la fois sur téléphone et sur ordinateur.

**10. "Rester connecté" contourne le verrouillage anti brute-force.**
`try_remember_me_login()` ne vérifie jamais `locked_until`. Un compte verrouillé après
plusieurs échecs de mot de passe reste donc accessible via un cookie "rester connecté"
émis avant le verrouillage — le lockout ne protège que le formulaire de mot de passe,
pas la reconnexion automatique.

**11. `devcontainer.json` désactive CORS et la protection CSRF de Streamlit** pour
Codespaces (`--server.enableCORS false --server.enableXsrfProtection false`). Isolé à
l'environnement de dev, donc pas un risque immédiat, mais dangereux si ce pattern de
commande est un jour copié-collé vers un déploiement réel.

### 🟢 Cosmétique / mineur

- `firebase_admin.auth` importé dans `temp_db_client.py` mais jamais utilisé (confirmé
  par `pyflakes`) — l'authentification est gérée "maison" via bcrypt, pas via Firebase
  Auth.
- Champ `role` stocké en session et en Firestore (`register`, `login`,
  `try_remember_me_login`) mais **jamais lu** pour un quelconque contrôle d'accès —
  fonctionnalité admin fantôme, jamais branchée.
- `xlrd` (lecture de `.xls`, jamais utilisé — l'export ne fait qu'écrire du `.xlsx` via
  `openpyxl`) et `matplotlib` (aucun `import matplotlib` direct dans le code
  applicatif — les graphiques passent tous par `plotly`) alourdissent
  `requirements.txt` sans être réellement utilisés par l'app elle-même.
- `db.log_donation_click(...)` renvoie un booléen que `app.py` n'exploite jamais : si
  l'écriture Firestore échoue, l'utilisateur voit quand même le message "Merci !".
- `if not self.db: return ...` (plusieurs méthodes de `temp_db_client.py`) est une
  condition qui ne peut jamais être vraie avec le flux actuel de `__init__` (si la
  connexion Firebase échoue, `st.stop()` est appelé avant que `self.db` existe) — code
  défensif mort, sans impact réel.
- Effet de bord du composant `CookieManager` : au tout premier rendu du script après
  ouverture de l'onglet, `cookie_manager.get()` renvoie `None` le temps d'un
  aller-retour JS→Python (comportement documenté de `extra-streamlit-components`), donc
  un flash furtif de l'écran de connexion peut apparaître avant que l'auto-reconnexion
  ne se déclenche au rerun suivant. Pas un vrai bug, mais une UX imparfaite.
- La regex email (`EMAIL_REGEX`) autorise théoriquement un `:` dans l'adresse (elle
  exclut seulement `@` et les espaces) ; le cookie "rester connecté" utilise `:` comme
  séparateur (`email:token`) — un email avec `:` casserait ce parsing. Cas extrême, peu
  prioritaire.

---

## Ce que j'ai pu tester en runtime vs uniquement en statique

**Réellement exécuté :**
- `pip install -r requirements.txt` dans un venv jetable → succès complet.
- `import prophet` isolé dans ce venv → succès.
- `streamlit run app.py` → serveur démarré, requête HTTP réelle → 200 OK, logs
  observés sans erreur, puis serveur arrêté et port vérifié libre.
- `python -m py_compile` sur tous les `.py` du dépôt.
- `pyflakes` sur tous les modules.
- Recherche exhaustive de fichiers de secrets dans l'historique git
  (`git log --all --diff-filter=A/D`, `git log -S`) sans jamais réafficher leur contenu
  après l'incident initial.
- Validation du format de `.streamlit/secrets.toml` via `tomllib` (structure
  uniquement, aucune valeur affichée après l'incident).

**Uniquement relu en statique (pas exécuté) :**
- Le flux "utilisateur connecté" dans son ensemble : connexion avec identifiants
  réels, tableau de bord, graphiques, alertes, export CSV/Excel, page Investissements.
  Je n'ai créé **aucun compte de test** et je ne me suis **pas connecté**, car
  `.streamlit/secrets.toml` pointe vers un projet Firebase de **production** réel — je
  n'ai pas voulu écrire de données de test dans une base réelle sans autorisation
  explicite. Le bouton "Faire un don" n'a pas été cliqué (aurait écrit dans
  `donation_clicks` en prod).
- Le scan OCR (`pytesseract`) : **Tesseract n'est pas installé sur cette machine**
  (`C:\Program Files\Tesseract-OCR\tesseract.exe` absent, et `tesseract` absent du
  PATH — confirmé). Le code gère ce cas via son `try/except` générique (qui afficherait
  l'erreur brute, cf. bug #7), mais je n'ai pas pu l'observer réellement se déclencher.
- Le comportement réel du cookie "rester connecté" dans un navigateur (pose, lecture au
  rechargement, suppression à la déconnexion) : aucun navigateur piloté n'a été utilisé
  dans cet audit. L'analyse du flux remember-me (bugs #9, #10, et le point cosmétique
  sur le flash au premier rendu) est une revue de code, pas un test de bout en bout.
- Le calcul de prévision Prophet (`forecast_prophet`) : l'import réussit, mais
  `Prophet().fit()` n'a jamais été appelé (nécessiterait des données réelles via
  connexion), donc le comportement du backend CmdStan au premier ajustement de modèle
  (téléchargement/compilation éventuelle au runtime) n'a pas été vérifié.
- Les règles de sécurité Firestore : **aucun fichier `firestore.rules` n'existe dans ce
  dépôt**, donc rien à inspecter statiquement. Point d'architecture à noter : l'app
  accède à Firestore exclusivement via le SDK Admin (compte de service, côté serveur
  Streamlit) — ce chemin d'accès **ignore totalement les règles de sécurité Firestore**
  (elles ne s'appliquent qu'aux SDK clients). Autrement dit, tout le contrôle d'accès
  de cette application repose à 100 % sur le code Python (`users.py`,
  `temp_db_client.py`) et sur la confidentialité de la clé privée du compte de
  service — pas sur des règles Firestore. C'est cohérent avec l'architecture choisie,
  mais ça veut dire que la clé privée est *le* point de confiance unique de toute
  l'application (d'où la gravité du point "À traiter en priorité" plus haut).

---

## Idées d'amélioration produit

Fonctionnalités qui manquent, à mon avis, pour qu'un usage quotidien réel en FCFA soit
confortable (au-delà des bugs ci-dessus) :

1. **Mode dégradé / file d'attente hors-ligne.** La connectivité mobile est souvent
   instable en Afrique de l'Ouest ; aujourd'hui, toute action (connexion, ajout de
   transaction) exige une réponse Firestore synchrone immédiate, sans aucun repli. Un
   tampon local qui se synchronise dès que la connexion revient éviterait de perdre une
   saisie faite en zone mal couverte.
2. **Budgets par catégorie avec plafond mensuel.** L'alerte actuelle (`alert_expense`)
   ne signale qu'une dépense ponctuelle élevée. Un vrai suivi "il te reste X FCFA sur
   ton budget Alimentation ce mois-ci" serait plus actionnable au quotidien qu'un seuil
   global unique.
3. **Transactions récurrentes** (loyer, abonnements, salaire). Aujourd'hui chaque
   transaction doit être ressaisie manuellement chaque mois — un modèle "récurrence"
   avec rappel automatique correspondrait mieux à des dépenses fixes typiques
   (loyer, factures).
4. **Réinitialisation de mot de passe réellement en libre-service.** Le flux actuel
   demande d'aller chercher le code manuellement dans la console Firestore et de le
   transmettre soi-même à l'utilisateur — ça ne passe pas à l'échelle, même pour
   quelques dizaines d'utilisateurs réels. Un envoi par SMS/WhatsApp (canaux plus
   fiables qu'email dans ce contexte) serait plus réaliste qu'un service d'email.
5. **Objectifs d'épargne à court terme avec barre de progression** (ex. "100 000 FCFA
   pour la rentrée scolaire d'ici 3 mois"). Le simulateur d'intérêts composés actuel est
   orienté investissement long terme ; un objectif concret et court terme correspond
   souvent mieux à un usage budget FCFA au quotidien.
6. **Budget partagé à plusieurs (foyer).** Chaque compte est aujourd'hui totalement
   isolé ; gérer un budget de ménage à plusieurs (courant dans les familles élargies)
   n'est pas possible sans partager un seul compte/mot de passe, ce qui est risqué vu
   le bug #1 sur l'isolation des données.
7. **Export PDF simple, lisible sur téléphone.** L'export actuel (CSV/Excel) cible plutôt
   un usage "comptable sur PC" ; un résumé mensuel en PDF, pensé pour être lu ou
   partagé depuis un smartphone, serait plus utile au quotidien pour la cible visée.

---

## Recommandations, priorisées

1. **Régénérer la clé de compte de service Firebase** dans la console Firebase, et la
   remplacer partout où elle est utilisée (`.streamlit/secrets.toml` local, secrets
   Streamlit Cloud). À faire quel que soit le résultat du point suivant.
2. **Corriger la collision d'uid** (`email.replace('.', '_').replace('@', '_at_')`) :
   utiliser l'email complet en minuscule (ou un hash) comme identifiant de collection.
   C'est le bug le plus grave du point de vue confidentialité des données.
3. Vérifier si ce dépôt a été public/forké pendant la période où `firebase_key.json` /
   `FIREBASE_SECRE.json` étaient trackés ; si oui, envisager une réécriture de
   l'historique git (BFG Repo-Cleaner ou `git filter-repo`) en plus de la rotation de
   clé.
4. Ajouter `investments.py` à `MODULES_TO_CHECK` dans
   `.github/scripts/check_imports.py`.
5. Protéger `get_entries()` (deuxième fallback) et `prepare_data()` contre les
   documents incomplets/l'indisponibilité réseau, pour éviter un crash brut de page —
   s'inspirer du pattern déjà utilisé dans `investments.py`.
6. Remplacer `except ImportError` par `except Exception` (avec message adapté) autour
   de l'import dynamique de `investments.py` dans `app.py`.
7. Uniformiser la gestion d'erreurs : ne plus afficher `{e}` brut dans `forms.py`
   (OCR) et `temp_db_client.py` (`add_entry`), comme c'est déjà fait ailleurs.
8. Remember-me : vérifier `locked_until` dans `try_remember_me_login`, et envisager un
   jeton par appareil (sous-collection `remember_tokens` au lieu d'un champ unique sur
   le document utilisateur) pour ne pas déconnecter silencieusement les autres
   appareils.
9. Nettoyage mineur : retirer l'import `auth` inutilisé, retirer `xlrd`/`matplotlib` de
   `requirements.txt` (sauf besoin futur explicite), corriger `.streamlit/secrets.toml`
   local au format TOML attendu (cf. `.streamlit/secrets.toml.example`) pour permettre
   de futurs tests locaux complets.
