import streamlit as st

def login():
    st.sidebar.header("Connexion")
    # Utilisation d'un conteneur pour le formulaire de connexion
    with st.sidebar.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter")

    if submitted:
        # **ATTENTION: Ceci est un exemple local.** # Pour une version production, utilisez Firebase Authentication.
        users = {
            "admin@example.com": {"password":"1234", "role":"admin"},
            "comptable@example.com": {"password":"abcd", "role":"comptable"}
        }
        if email in users and users[email]["password"]==password:
            st.session_state['user'] = email
            st.session_state['role'] = users[email]["role"]
            st.success(f"Connecté : {email}")
            # Rerun pour rafraîchir le dashboard
            st.rerun()
        else:
            st.error("Email ou mot de passe incorrect")

def logout():
    if 'user' in st.session_state:
        st.sidebar.button("Déconnexion", on_click=_do_logout)

def _do_logout():
    # Supprime les clés de session
    if 'user' in st.session_state:
        del st.session_state['user']
    if 'role' in st.session_state:
        del st.session_state['role']
    st.rerun()