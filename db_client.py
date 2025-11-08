import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import streamlit as st

class DBClient:
    def __init__(self, firebase_key_path="firebase_key.json"):
        try:
            # Assurez-vous que l'application n'est initialisée qu'une seule fois
            cred = credentials.Certificate(firebase_key_path)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
        except Exception as e:
            st.error(f"Erreur Firebase : Vérifiez votre fichier 'firebase_key.json'. Détail: {e}")
            self.db = None

    def add_entry(self, collection, entry):
        if not self.db: return False
        # Ajoute l'horodatage de création
        entry['timestamp'] = datetime.now()
        self.db.collection(collection).add(entry)
        return True

    def get_entries(self, collection):
        if not self.db: return []
        # Récupère et ordonne par date
        docs = self.db.collection(collection).order_by("timestamp").stream()
        data = []
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            data.append(d)
        return data

    def update_entry(self, collection, doc_id, new_entry):
        if not self.db: return False
        self.db.collection(collection).document(doc_id).update(new_entry)
        return True

    def delete_entry(self, collection, doc_id):
        if not self.db: return False
        self.db.collection(collection).document(doc_id).delete()
        return True