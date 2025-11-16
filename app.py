import streamlit as st
import firebase_admin
from firebase_admin import credentials, auth
import json # Importation nécessaire pour lire la chaîne JSON

# --- CONFIGURATION DE PAGE ---
st.set_page_config(layout="centered", page_title="Budget App")

# --- Initialisation de Firebase (MÉTHODE ROBUSTE FIXÉE) ---

def initialize_firebase():
    """
    Initialise l'application Firebase en utilisant la chaîne JSON complète
    stockée sous FIREBASE_SECRET dans les secrets Streamlit.
    """
    if not firebase_admin._apps:
        try:
            # 1. Vérifie si la clé 'FIREBASE_SECRET' existe (Utilise le nom correct)
            if "FIREBASE_SECRET" not in st.secrets:
                st.error("Erreur de configuration: La clé 'FIREBASE_SECRET' est manquante dans les secrets Streamlit.")
                st.info("Veuillez vous assurer que votre fichier secrets.toml contient la clé FIREBASE_SECRET avec la configuration JSON.")
                st.stop()
                
            # 2. Récupère la CHAÎNE JSON
            json_string = st.secrets["FIREBASE_SECRET"]
            
            # 3. Parse la CHAÎNE JSON en Dictionnaire Python (CRITIQUE pour le format triple-guillemets)
            key_dict = json.loads(json_string)
            
            # NOTE: La conversion des '\n' n'est plus nécessaire ici car json.loads le gère
            # si la clé privée est correctement échappée dans la chaîne JSON.
            
            # 4. Initialise l'application Firebase avec le dictionnaire
            cred = credentials.Certificate(key_dict)
            firebase_admin.initialize_app(cred)
            st.success("Connexion Firebase établie avec succès!")

        except json.JSONDecodeError as e:
            # Gère les erreurs si la chaîne FIREBASE_SECRET n'est pas un JSON valide
            st.error(f"Erreur de PARSING JSON: {e}")
            st.info("Le contenu de FIREBASE_SECRET n'est pas un JSON valide. Veuillez vérifier la syntaxe (guillemets, virgules).")
            st.stop()
        except Exception as e:
            # Capture l'erreur "Invalid private key" si elle survient après le parsing
            st.error(f"Erreur CRITIQUE lors de l'initialisation de Firebase: {e}")
            st.info("Le contenu JSON est peut-être correct, mais la clé privée elle-même est mal formée. Confirmez que le fichier JSON téléchargé depuis Firebase est complet.")
            st.stop()

# Lance l'initialisation au démarrage
initialize_firebase()

# --- Fonctions des pages de l'application ---

def login_page():
    st.title("💸 Budget App - Connexion")
    
    st.subheader("Authentification")
    
    # Sélecteur pour choisir entre Se connecter et S'inscrire
    auth_mode = st.radio("Choisissez l'action :", ["Se connecter", "S'inscrire"])
    
    with st.form("auth_form"):
        email = st.text_input("Email")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button(auth_mode)

    if submitted:
        try:
            if auth_mode == "S'inscrire":
                # Vérifie la longueur du mot de passe (min. 6 caractères pour Firebase)
                if len(password) < 6:
                    st.error("Échec de l'inscription: Le mot de passe doit contenir au moins 6 caractères.")
                else:
                    user = auth.create_user(email=email, password=password)
                    st.success(f"Inscription réussie pour l'utilisateur : {user.uid}!")
                    # Connexion automatique après l'inscription
                    st.session_state['user_info'] = auth.get_user(user.uid)
                    st.session_state['logged_in'] = True
                    st.rerun()
            
            elif auth_mode == "Se connecter":
                # NOTE: Utiliser l'API Admin pour simuler la connexion est une simplification.
                # Dans une vraie app, l'utilisateur final utiliserait l'API client pour se connecter directement.
                # Ici, nous vérifions simplement que l'utilisateur existe par son email.
                try:
                    user = auth.get_user_by_email(email)
                    st.success("Connexion simulée réussie!")
                    st.session_state['user_info'] = user
                    st.session_state['logged_in'] = True
                    st.rerun()
                except firebase_admin.exceptions.FirebaseError:
                    st.error("Échec de la connexion: Email non trouvé (vérifiez l'email et le mot de passe).")
                
        except firebase_admin.exceptions.FirebaseError as e:
            # Gère les erreurs spécifiques
            error_message = str(e)
            if "email address is already in use" in error_message:
                st.error("Échec de l'inscription: L'email est déjà utilisé. Veuillez vous connecter ou utiliser un autre email.")
            elif "The email address is badly formatted" in error_message or "Invalid email" in error_message:
                st.error("Échec de l'inscription/Connexion: L'adresse email est mal formatée.")
            elif "Password should be at least 6 characters" in error_message:
                 st.error("Échec de l'inscription: Le mot de passe doit contenir au moins 6 caractères.")
            else:
                st.error(f"Échec de l'inscription/Connexion: {error_message}")


def dashboard_page():
    st.title(f"Tableau de Bord de {st.session_state.user_info.email}")
    st.write("C'est ici que vous gérerez vos budgets et dépenses.")
    
    st.markdown("---")
    
    st.subheader("Informations Utilisateur")
    st.write(f"ID Utilisateur (UID): `{st.session_state.user_info.uid}`")
    
    st.info("Fonctionnalités de gestion du budget à venir...")
    
    st.markdown("---")

    if st.button("Déconnexion", type="primary"):
        st.session_state['logged_in'] = False
        st.session_state['user_info'] = None
        st.success("Déconnexion réussie. Redirection vers la page de connexion.")
        st.rerun()

# --- Logique de l'Application Principale ---

# Initialisation des états de session
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None

# Affichage conditionnel des pages
if st.session_state['logged_in']:
    dashboard_page()
else:
    login_page()