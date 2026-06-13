import streamlit as st
from passlib.hash import sha256_crypt

# --- FONCTION DE CONNEXION ---
def login(email, password, db):
    """Gère la connexion de l'utilisateur avec validation stricte."""
    if not email or not password:
        st.error("Veuillez remplir tous les champs.")
        return

    email = email.lower().strip() # Nettoyage de l'email
    
    try:
        user_data = db.get_user(email) 
        if user_data:
            # Vérification sécurisée
            if sha256_crypt.verify(password, user_data.get('password_hash', '')):
                st.session_state['user'] = email
                st.session_state['role'] = user_data.get('role', 'user')
                # Création d'un UID propre pour les collections Firestore
                st.session_state['uid'] = email.replace('.', '_').replace('@', '_at_')
                
                st.success(f"Bienvenue, {email} !")
                st.rerun()
            else:
                st.error("Identifiants incorrects.")
        else:
            st.error("Identifiants incorrects.")
    except Exception as e:
        st.error(f"Erreur système lors de la connexion.")

# --- FONCTION D'INSCRIPTION ---
def register(email, password, db, role="user"):
    """Gère l'inscription avec vérification de format."""
    if not email or len(password) < 6:
        st.error("L'email est requis et le mot de passe doit faire 6 caractères min.")
        return False

    email = email.lower().strip()
    
    # Vérification si l'utilisateur existe déjà
    if db.get_user(email):
        st.warning("Cet email est déjà utilisé.")
        return False
        
    hashed_password = sha256_crypt.hash(password)

    new_user_data = {
        "email": email,
        "password_hash": hashed_password, 
        "role": role,
        "created_at": st.date_input("Date du jour", disabled=True) # Log de sécurité
    }

    if db.save_user(email, new_user_data):
        st.success("Compte créé avec succès ! Connectez-vous maintenant.")
        return True
    return False

# --- FONCTION DE DÉCONNEXION ---
def logout():
    """Nettoyage complet de la session."""
    if st.sidebar.button("Déconnexion", key="logout_btn"):
        # On vide tout le dictionnaire de session pour la sécurité
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()