import firebase_admin
from firebase_admin import credentials, firestore, auth
import streamlit as st

class DBClient:
    def __init__(self):
        if not firebase_admin._apps:
            try:
                # Utilisation sécurisée des secrets Streamlit
                key_dict = dict(st.secrets["firebase"])
            except (KeyError, FileNotFoundError):
                st.error(
                    "❌ Secret Firebase absent : la section [firebase] est introuvable dans "
                    ".streamlit/secrets.toml. Copie .streamlit/secrets.toml.example vers "
                    ".streamlit/secrets.toml (ou configure les secrets sur Streamlit Cloud) "
                    "et renseigne tes vraies valeurs."
                )
                st.stop()

            try:
                if "private_key" in key_dict:
                    key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")

                cred = credentials.Certificate(key_dict)
                firebase_admin.initialize_app(cred)

            except Exception:
                # On n'affiche jamais le détail brut de l'exception : il peut
                # contenir des fragments de la clé privée Firebase.
                st.error(
                    "❌ Clé Firebase invalide : la section [firebase] existe mais son contenu "
                    "est mal formé ou incomplet. Vérifie que chaque champ de "
                    ".streamlit/secrets.toml correspond bien au JSON de la clé de service "
                    "Firebase (notamment private_key)."
                )
                st.stop() # On arrête tout si la DB ne répond pas

        self.db = firestore.client()

    # --- GESTION UTILISATEURS ---

    def get_user(self, email):
        """Récupère les infos de l'utilisateur."""
        if not self.db: return None
        try:
            doc_ref = self.db.collection('users').document(email.lower()) # Toujours en minuscule pour éviter les doublons
            doc = doc_ref.get()
            return doc.to_dict() if doc.exists else None
        except Exception:
            return None

    def save_user(self, email, user_data):
        """Enregistre (écrase) le document utilisateur complet avec mise en minuscule de l'email."""
        if not self.db: return False
        try:
            # On s'assure que l'email est l'ID du document en minuscules
            self.db.collection('users').document(email.lower()).set(user_data)
            return True
        except Exception:
            st.error("Erreur lors de la sauvegarde du compte.")
            return False

    def update_user(self, email, updates):
        """Met à jour partiellement le profil utilisateur sans écraser les autres champs
        (contrairement à save_user, qui remplace tout le document)."""
        if not self.db: return False
        try:
            self.db.collection('users').document(email.lower()).set(updates, merge=True)
            return True
        except Exception:
            st.error("Erreur lors de la mise à jour du profil.")
            return False

    # --- GESTION BUDGET (OPTIMISÉE) ---

    def add_entry(self, collection, entry):
        """Ajoute une transaction avec horodatage automatique."""
        if not self.db: return False
        try:
            # Ajout d'un timestamp serveur pour un tri précis plus tard
            entry['server_timestamp'] = firestore.SERVER_TIMESTAMP
            self.db.collection(collection).add(entry)
            return True
        except Exception as e:
            st.error(f"Erreur d'ajout : {e}")
            return False

    def get_entries(self, collection):
        """Récupère les transactions triées par date de création."""
        if not self.db: return []
        try:
            # Tri par date pour éviter que l'application ne mélange les transactions
            docs = self.db.collection(collection).order_by('server_timestamp', direction=firestore.Query.DESCENDING).stream()
            return [{**doc.to_dict(), 'id': doc.id} for doc in docs]
        except Exception:
            # Si le tri échoue (ex: pas de timestamp sur les vieilles entrées), on récupère tout sans tri
            docs = self.db.collection(collection).stream()
            return [{**doc.to_dict(), 'id': doc.id} for doc in docs]