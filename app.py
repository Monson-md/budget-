import streamlit as st
from db_client import FirebaseClient
import json
from datetime import datetime
import pandas as pd
import plotly.express as px

# Initialisation du client Firebase
# Tente de récupérer les secrets. Si l'application tourne sur Streamlit Cloud,
# les secrets sont lus depuis l'interface Streamlit.
try:
    if st.secrets.get("FIREBASE_SECRET"):
        firebase_config = json.loads(st.secrets["FIREBASE_SECRET"])
    else:
        # Ceci est pour les tests locaux si vous n'avez pas de fichier .streamlit/secrets.toml
        # Si vous testez en local, vous devrez peut-être adapter cette partie.
        st.error("Le secret 'FIREBASE_SECRET' n'a pas été trouvé. Assurez-vous qu'il est configuré.")
        firebase_config = None 
except Exception as e:
    st.error(f"Erreur de chargement des secrets Firebase: {e}")
    firebase_config = None

if firebase_config:
    db = FirebaseClient(firebase_config)
else:
    # Si la configuration a échoué, on utilise un client fictif pour éviter les erreurs de crash
    class DummyClient:
        def __init__(self):
            st.warning("Client de base de données non initialisé en raison d'une erreur de configuration.")
            self.user_data = {}
        def sign_up(self, email, password): return {"success": False, "message": "DB non configurée."}
        def sign_in(self, email, password): return {"success": False, "message": "DB non configurée."}
        def get_all_transactions(self, user_id): return []
        def add_transaction(self, user_id, type, amount, category, date, description): return {"success": False}
    db = DummyClient()


# --- Fonctions d'authentification ---

def sign_up_form():
    """Affiche le formulaire d'inscription."""
    st.title("💸 Inscription")
    email = st.text_input("Email", key="signup_email")
    password = st.text_input("Mot de passe", type="password", key="signup_password")
    if st.button("S'inscrire"):
        if email and password:
            result = db.sign_up(email, password)
            if result["success"]:
                st.success("Inscription réussie. Vous pouvez maintenant vous connecter.")
            else:
                st.error(f"Échec de l'inscription: {result['message']}")
        else:
            st.error("Veuillez remplir tous les champs.")

def sign_in_form():
    """Affiche le formulaire de connexion."""
    st.title("🔑 Connexion")
    email = st.text_input("Email", key="signin_email")
    password = st.text_input("Mot de passe", type="password", key="signin_password")
    if st.button("Se connecter"):
        if email and password:
            result = db.sign_in(email, password)
            if result["success"]:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = result["user_id"]
                st.session_state["user_email"] = email
                st.rerun()
            else:
                st.error(f"Échec de la connexion: {result['message']}")
        else:
            st.error("Veuillez remplir tous les champs.")

def sign_out():
    """Déconnecte l'utilisateur et réinitialise la session."""
    if "logged_in" in st.session_state:
        del st.session_state["logged_in"]
    if "user_id" in st.session_state:
        del st.session_state["user_id"]
    if "user_email" in st.session_state:
        del st.session_state["user_email"]
    st.success("Déconnexion réussie.")
    st.rerun()

# --- Fonctions du Tableau de Bord ---

def add_transaction_form():
    """Affiche le formulaire pour ajouter une nouvelle transaction."""
    st.subheader("➕ Ajouter une nouvelle transaction")
    
    with st.form("transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            transaction_type = st.radio("Type", ["Dépense", "Revenu"], horizontal=True)
            amount = st.number_input("Montant", min_value=0.01, format="%.2f")
            date = st.date_input("Date", datetime.now().date())

        with col2:
            categories_depense = ["Nourriture", "Logement", "Transport", "Loisirs", "Santé", "Autres Dépenses"]
            categories_revenu = ["Salaire", "Investissement", "Cadeau", "Autres Revenus"]
            
            if transaction_type == "Dépense":
                category = st.selectbox("Catégorie", categories_depense)
            else:
                category = st.selectbox("Catégorie", categories_revenu)
                
            description = st.text_area("Description (optionnel)")
            
        submitted = st.form_submit_button("Enregistrer la transaction")

        if submitted:
            user_id = st.session_state["user_id"]
            
            # Correction: Assurez-vous que l'amount est positif avant l'enregistrement
            # Le type est géré par la base de données pour la négativité.
            
            result = db.add_transaction(
                user_id=user_id,
                type=transaction_type,
                amount=amount,
                category=category,
                date=date.isoformat(), # Sauvegarder la date au format string ISO
                description=description
            )
            
            if result["success"]:
                st.success("Transaction enregistrée avec succès !")
            else:
                st.error(f"Erreur lors de l'enregistrement: {result['message']}")

def display_dashboard():
    """Affiche le tableau de bord principal de l'utilisateur."""
    st.title(f"🏠 Tableau de Bord de Budget")
    
    user_id = st.session_state["user_id"]
    st.sidebar.caption(f"Connecté en tant que : **{st.session_state['user_email']}**")
    st.sidebar.button("Déconnexion", on_click=sign_out)

    # 1. Chargement des données
    transactions_list = db.get_all_transactions(user_id)
    
    if not transactions_list:
        st.info("Aucune transaction enregistrée pour le moment. Ajoutez votre première transaction ci-dessous.")
        add_transaction_form()
        return

    # 2. Préparation du DataFrame
    df = pd.DataFrame(transactions_list)
    df['date'] = pd.to_datetime(df['date'])
    df['amount_signed'] = df.apply(
        lambda row: -row['amount'] if row['type'] == 'Dépense' else row['amount'], 
        axis=1
    )
    df = df.sort_values(by='date', ascending=False)
    
    # 3. Métriques clés (KIPs)
    total_revenu = df[df['type'] == 'Revenu']['amount'].sum()
    total_depense = df[df['type'] == 'Dépense']['amount'].sum()
    solde = total_revenu - total_depense
    
    st.subheader("Résumé de la performance")
    colA, colB, colC = st.columns(3)
    
    with colA:
        st.metric("Total Revenu ⬆️", f"{total_revenu:,.2f} €", delta_color="off")
    with colB:
        st.metric("Total Dépense ⬇️", f"-{total_depense:,.2f} €", delta_color="off")
    with colC:
        solde_delta = "Aucun changement" if solde == 0 else f"{solde:,.2f} €"
        st.metric("Solde Net ⚖️", f"{solde:,.2f} €", delta_color="off")
        
    st.markdown("---")
    
    # 4. Visualisation (Dépenses par Catégorie)
    st.subheader("Analyse des Dépenses")
    
    depenses_df = df[df['type'] == 'Dépense'].groupby('category')['amount'].sum().reset_index()
    if not depenses_df.empty:
        fig = px.pie(
            depenses_df, 
            values='amount', 
            names='category', 
            title='Répartition des Dépenses par Catégorie',
            hole=.3
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aucune dépense à analyser.")

    st.markdown("---")
    
    # 5. Formulaire d'ajout (positionné ici pour la clarté)
    add_transaction_form()

    st.markdown("---")
    
    # 6. Tableau des transactions récentes
    st.subheader("Historique des transactions")
    # Affichage des transactions sans les IDs Firestore
    display_df = df[['date', 'type', 'category', 'amount_signed', 'description']]
    display_df.columns = ['Date', 'Type', 'Catégorie', 'Montant (€)', 'Description']
    
    st.dataframe(display_df, use_container_width=True)


# --- Routage de l'Application ---

def main():
    st.set_page_config(page_title="Budget App", layout="wide", initial_sidebar_state="collapsed")
    
    # Initialisation de l'état de session si non défini
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["user_id"] = None
        st.session_state["page"] = "sign_in"

    if st.session_state["logged_in"]:
        display_dashboard()
    else:
        # Barre latérale pour changer de mode (Connexion/Inscription)
        st.sidebar.title("Navigation")
        if st.sidebar.button("Se connecter 🔑", disabled=(st.session_state["page"] == "sign_in")):
            st.session_state["page"] = "sign_in"
            st.rerun()
        if st.sidebar.button("S'inscrire 💸", disabled=(st.session_state["page"] == "sign_up")):
            st.session_state["page"] = "sign_up"
            st.rerun()

        # Affichage du formulaire de connexion ou d'inscription
        if st.session_state["page"] == "sign_up":
            sign_up_form()
        else: # Default is sign_in
            sign_in_form()

if __name__ == "__main__":
    main()