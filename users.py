import streamlit as st # <-- Correction ici (on retire le 'c')
from passlib.hash import sha256_crypt
# db_client n'est pas importé ici car il est passé en argument depuis app.py

# --- FONCTION DE CONNEXION (MISE À JOUR) ---
def login(email, password, db):
    """Gère la connexion de l'utilisateur et vérifie le hash du mot de passe."""
    try:
        # 1. Récupération des données utilisateur via db_client
        user_data = db.get_user(email) 
        if user_data:
            # 2. Vérification du mot de passe haché avec passlib
            # .verify compare le mot de passe clair avec le hash stocké
            if sha256_crypt.verify(password, user_data.get('password_hash', '')):
                st.session_state['user'] = email
                st.session_state['role'] = user_data.get('role', 'user')
                st.success(f"Connexion réussie pour {email} !")
                st.rerun()
            else:
                st.error("Email ou mot de passe incorrect.")
        else:
            st.error("Email ou mot de passe incorrect.")
    except Exception as e:
        # Cela pourrait être une erreur de connexion à la BDD
        st.error(f"Erreur de connexion : {e}")


# --- FONCTION D'INSCRIPTION (NOUVELLE) ---
def register(email, password, db, role="user"):
    """Gère l'inscription de l'utilisateur, hachage et sauvegarde dans Firestore."""
    
    # 1. Vérification de l'existence
    user_data = db.get_user(email)
    if user_data:
        st.warning("Cet email est déjà enregistré. Veuillez vous connecter.")
        return False
        
    # 2. Hachage du mot de passe avec sha256_crypt de passlib
    hashed_password = sha256_crypt.hash(password)

    # 3. Préparation des données et sauvegarde
    new_user_data = {
        "email": email,
        "password_hash": hashed_password, 
        "role": role 
    }

    try:
        db.save_user(email, new_user_data) 
        st.success("Inscription réussie ! Vous pouvez maintenant vous connecter.")
        return True
    except Exception as e:
        st.error(f"Erreur lors de l'inscription : {e}")
        return False


# --- FONCTION DE DÉCONNEXION (À GARDER) ---
def logout():
    """Ajoute le bouton de déconnexion dans la barre latérale."""
    if st.sidebar.button("Déconnexion"):
        if 'user' in st.session_state:
            del st.session_state['user']
        if 'role' in st.session_state:
            del st.session_state['role']
        st.rerun()