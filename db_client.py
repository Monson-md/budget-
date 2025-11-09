# db_client.py (Assurez-vous que cette classe contient les fonctions suivantes)

# ... (votre code d'initialisation de Firebase)

class DBClient:
    def __init__(self):
        # ... (votre code d'initialisation de Firebase Admin SDK)
        self.db = firestore.client() # L'instance de la base de données

    # --- NOUVELLE FONCTION 1 : Récupérer un utilisateur ---
    def get_user(self, email):
        """Récupère les données d'un utilisateur par son email (ID du document)."""
        # Chemin de la collection : /artifacts/{appId}/users/{userId}/users
        # Pour les utilisateurs, nous utilisons l'email comme ID pour la collection 'users'
        # Assurez-vous d'avoir une collection 'users' au bon emplacement. 
        # Si vous utilisez un chemin spécifique pour les utilisateurs, ajustez ici.
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

    # ... (vos fonctions existantes : add_entry, get_entries, etc.)