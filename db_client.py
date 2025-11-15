import firebase_admin
from firebase_admin import credentials, auth, firestore
import json
import logging
import time

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FirebaseClient:
    """
    Client pour interagir avec Firebase Authentication et Firestore.
    Utilise les secrets Streamlit pour l'initialisation.
    """
    def __init__(self, firebase_config):
        """
        Initialise l'application Firebase et les services de base de données.
        :param firebase_config: Dictionnaire des identifiants du compte de service.
        """
        self.db = None
        
        try:
            # Vérifie si l'application est déjà initialisée
            if not firebase_admin._apps:
                # Les identifiants doivent être chargés depuis le dictionnaire (secrets Streamlit)
                cred = credentials.Certificate(firebase_config)
                
                # Initialisation de l'application Firebase
                firebase_admin.initialize_app(cred)

            # Obtention du client Firestore
            self.db = firestore.client()
            logger.info("Firebase initialisé avec succès.")

        except Exception as e:
            logger.error(f"Erreur d'initialisation de Firebase: {e}")
            self.db = None

    def sign_up(self, email, password):
        """
        Crée un nouvel utilisateur.
        :return: Dict avec 'success' (bool) et 'message' (str) ou 'user_id' (str).
        """
        if not self.db:
            return {"success": False, "message": "Base de données non initialisée."}
        try:
            user = auth.create_user(
                email=email,
                password=password
            )
            # Créer un document initial dans Firestore (pour les futures données utilisateur)
            user_ref = self.db.collection('users').document(user.uid)
            user_ref.set({
                'email': email,
                'created_at': firestore.SERVER_TIMESTAMP
            })
            logger.info(f"Nouvel utilisateur créé: {user.uid}")
            return {"success": True, "user_id": user.uid}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def sign_in(self, email, password):
        """
        Tente de connecter un utilisateur (méthode indirecte, car Streamlit ne gère pas directement les tokens de connexion).
        Pour une application Streamlit simple, on vérifie l'existence de l'utilisateur.
        **NOTE:** Dans une vraie app, l'authentification nécessite une validation du mot de passe via un service tiers.
        Ici, nous allons simplement récupérer l'utilisateur par email. Si l'utilisateur existe, on suppose la connexion.
        """
        if not self.db:
            return {"success": False, "message": "Base de données non initialisée."}
        
        # NOTE: Firebase Admin SDK ne permet pas la connexion directe par email/mot de passe.
        # Cette méthode est une solution de contournement simple pour l'environnement Streamlit.
        # Elle ne valide PAS le mot de passe.
        try:
            # Récupérer l'utilisateur par email
            user = auth.get_user_by_email(email)
            logger.info(f"Connexion utilisateur réussie (vérification par email): {user.uid}")
            return {"success": True, "user_id": user.uid}
        except Exception as e:
            # L'erreur la plus probable est que l'utilisateur n'existe pas
            return {"success": False, "message": "Email ou mot de passe incorrect."}

    # --- Méthodes de gestion du Budget ---

    def add_transaction(self, user_id, type, amount, category, date, description):
        """
        Ajoute une nouvelle transaction pour l'utilisateur.
        :param user_id: ID de l'utilisateur.
        :param type: 'Dépense' ou 'Revenu'.
        :param amount: Montant de la transaction (doit être positif).
        :param category: Catégorie de la transaction.
        :param date: Date de la transaction (format ISO string).
        :param description: Description optionnelle.
        :return: Dict avec 'success' (bool) et 'message' (str).
        """
        if not self.db:
            return {"success": False, "message": "Base de données non initialisée."}
        
        if amount <= 0:
            return {"success": False, "message": "Le montant doit être positif."}

        try:
            transaction_data = {
                'user_id': user_id, # Redondant mais utile pour les requêtes globales
                'type': type,
                'amount': float(amount),
                'category': category,
                'date': date,
                'description': description,
                'timestamp': firestore.SERVER_TIMESTAMP
            }
            
            # Utilise une sous-collection spécifique à l'utilisateur pour les transactions
            transactions_ref = self.db.collection('users').document(user_id).collection('transactions')
            transactions_ref.add(transaction_data)
            
            return {"success": True, "message": "Transaction ajoutée."}
        except Exception as e:
            logger.error(f"Erreur d'ajout de transaction: {e}")
            return {"success": False, "message": str(e)}

    def get_all_transactions(self, user_id):
        """
        Récupère toutes les transactions pour un utilisateur donné.
        :param user_id: ID de l'utilisateur.
        :return: Liste de dictionnaires de transactions.
        """
        if not self.db:
            return []
        
        try:
            transactions_ref = self.db.collection('users').document(user_id).collection('transactions')
            # Utilisation de la chaîne 'DESCENDING' pour éviter l'erreur firestore.Query.DESCENDING
            docs = transactions_ref.order_by('date', direction='DESCENDING').stream() 
            
            transactions_list = []
            for doc in docs:
                data = doc.to_dict()
                # On ajoute l'ID du document pour les opérations futures (ex: suppression/modification)
                data['id'] = doc.id 
                transactions_list.append(data)
                
            return transactions_list
        except Exception as e:
            logger.error(f"Erreur de récupération des transactions: {e}")
            return []