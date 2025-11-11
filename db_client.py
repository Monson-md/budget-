import os
import streamlit as st
import json
from firebase_admin import credentials, initialize_app, firestore

# --- MODIFICATION CLÉ : UTILISER LES SECRETS STREAMLIT ---
# La clé sera lue à partir de la variable d'environnement 'FIREBASE_SECRET'
# que vous configurerez sur Streamlit Cloud.

# Définition de la classe pour se connecter à Firestore
class DBClient:
    def __init__(self):
        # Initialisation de l'application Firebase
        if not initialize_app:
            st.error("Le SDK Firebase Admin n'a pas été importé correctement.")
            return

        # Tentative d'initialisation (nécessaire une seule fois)
        if not initialize_app.apps:
            try:
                # 1. Récupération de la clé secrète JSON depuis les secrets Streamlit
                # Nous utilisons st.secrets pour accéder aux variables d'environnement
                # ou l'environnement OS si nous sommes en local (méthode de secours).
                secret_json = st.secrets.get("FIREBASE_SECRET", os.getenv("FIREBASE_SECRET"))
                
                if not secret_json:
                    st.error("Erreur : La variable FIREBASE_SECRET est manquante dans les secrets Streamlit ou l'environnement.")
                    return
                
                # 2. Convertir la chaîne JSON en un dictionnaire (dict)
                # La variable d'environnement contient la clé JSON complète sous forme de chaîne.
                cred_dict = json.loads(secret_json)
                
                # 3. Créer les identifiants à partir du dictionnaire
                cred = credentials.Certificate(cred_dict)
                
                # 4. Initialiser l'application
                initialize_app(cred)
                st.info("Connexion Firebase établie avec les secrets.")
                
            except Exception as e:
                st.error(f"Erreur d'initialisation Firebase. Vérifiez la clé dans les secrets : {e}")
                return
        
        # Obtention du client Firestore
        self.db = firestore.client()

    # --- NOUVELLE FONCTION 1 : Récupérer un utilisateur ---
    def get_user(self, email):
        """Récupère les données d'un utilisateur par son email (ID du document)."""
        # Chemin de la collection : /artifacts/{appId}/users/{userId}/users
        doc_ref = self.db.collection('users').document(email) 
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    # --- NOUVELLE FONCTION 2 : Sauvegarder/Créer un utilisateur ---
    def save_user(self, email, user_data):
        """Sauvegarde les données de l'utilisateur (crée ou met à jour)."""
        doc_ref = self.db.collection('users').document(email)
        doc_ref.set(user_data)
        return True

    # --- Vos autres fonctions CRUD ---
    def add_entry(self, collection_name, data):
        """Ajoute une nouvelle entrée à une collection."""
        try:
            self.db.collection(collection_name).add(data)
            return True
        except Exception as e:
            st.error(f"Erreur lors de l'ajout de l'entrée : {e}")
            return False

    def get_entries(self, collection_name):
        """Récupère toutes les entrées d'une collection."""
        try:
            docs = self.db.collection(collection_name).stream()
            data = []
            for doc in docs:
                entry = doc.to_dict()
                entry['id'] = doc.id
                data.append(entry)
            return data
        except Exception as e:
            st.error(f"Erreur lors de la récupération des entrées : {e}")
            return []