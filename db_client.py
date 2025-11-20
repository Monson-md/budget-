import firebase_admin
from firebase_admin import credentials, firestore, auth
import streamlit as st

class DBClient:
    def __init__(self):
        # Vérifie si l'application est déjà initialisée pour éviter l'erreur "Default app already exists"
        if not firebase_admin._apps:
            try:
                # 1. Récupération directe du dictionnaire depuis les secrets
                # Streamlit convertit automatiquement la section [firebase] en dictionnaire
                key_dict = dict(st.secrets["firebase"])
                
                # 2. Correction critique des sauts de ligne dans la clé privée
                # Les \n sont parfois lus comme des caractères littéraux '\\n', il faut les remplacer
                if "private_key" in key_dict:
                    key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")

                # 3. Initialisation de l'application avec le dictionnaire
                cred = credentials.Certificate(key_dict)
                firebase_admin.initialize_app(cred)
                
            except Exception as e:
                st.error(f"Erreur d'initialisation Firebase : {e}")
                return

        # Obtention du client Firestore
        self.db = firestore.client()

    # --- GESTION UTILISATEURS ---

    def get_user(self, email):
        """Récupère les infos de l'utilisateur dans la collection 'users'."""
        if not self.db: return None
        doc_ref = self.db.collection('users').document(email)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    def save_user(self, email, user_data):
        """Enregistre un nouvel utilisateur."""
        if not self.db: return False
        self.db.collection('users').document(email).set(user_data)
        return True

    # --- GESTION BUDGET ---

    def add_entry(self, collection, entry):
        """Ajoute une transaction."""
        if not self.db: return False
        self.db.collection(collection).add(entry)
        return True

    def get_entries(self, collection):
        """Récupère les transactions."""
        if not self.db: return []
        docs = self.db.collection(collection).stream()
        return [{**doc.to_dict(), 'id': doc.id} for doc in docs]