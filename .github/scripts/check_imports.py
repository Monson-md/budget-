"""Vérifie, module par module, que chaque module non-entrypoint du projet
s'importe sans erreur avec les dépendances installées depuis requirements.txt.

Objectif : détecter en CI les incompatibilités de dépendances (ex. le bug
passlib/Python récent) avant le déploiement sur Streamlit Cloud, plutôt qu'en
production. app.py est volontairement exclu : c'est le point d'entrée
Streamlit, pas un module destiné à être importé isolément.
"""
import importlib
import os
import sys

# Le script vit dans .github/scripts/ ; on ajoute la racine du dépôt (où
# vivent les modules à tester) au sys.path pour que `import users` etc.
# fonctionne quel que soit le répertoire courant.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

MODULES_TO_CHECK = [
    "users",
    "temp_db_client",
    "currency",
    "utils",
    "analysis",
    "forms",
    "investments",
]

def main():
    failures = []
    for module_name in MODULES_TO_CHECK:
        try:
            importlib.import_module(module_name)
            print(f"OK   - {module_name}")
        except Exception as exc:
            failures.append((module_name, exc))
            print(f"FAIL - {module_name}: {exc!r}")

    if failures:
        print(f"\n{len(failures)} module(s) n'ont pas pu être importés :")
        for module_name, exc in failures:
            print(f"  - {module_name}: {exc}")
        sys.exit(1)

    print(f"\nLes {len(MODULES_TO_CHECK)} modules se sont importés avec succès.")

if __name__ == "__main__":
    main()
