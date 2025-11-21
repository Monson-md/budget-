import streamlit as st
# Les imports CRITIQUES qui appellent vos autres fichiers
from temp_db_client import DBClient 
from forms import entry_form
from analysis import prepare_data, forecast_prophet
from plots import plot_revenue_expense, plot_profit_margin
from utils import export_csv, export_pdf, alert_expense
from users import login, register, logout 

import pandas as pd

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Budget App", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- INITIALISATION DE LA BASE DE DONNÉES ---
# L'initialisation de Firebase et Firestore se fait dans la classe DBClient.
if 'db' not in st.session_state:
    try:
        # L'exécution de DBClient() tente de se connecter via le secret FIREBASE_SECRET
        st.session_state['db'] = DBClient()
    except Exception as e:
        # DBClient affiche ses propres erreurs de connexion si le secret est mal formaté
        st.error(f"Erreur d'initialisation du client DB: {e}")
        st.stop()

db = st.session_state['db']

# Vérification si la connexion Firebase a échoué dans DBClient
if not db.db: 
    # Si db.db est None (car l'initialisation a échoué dans __init__ de DBClient)
    st.info("La configuration Firebase a échoué. Veuillez vérifier le secret FIREBASE_SECRET dans Streamlit Cloud.")
    st.stop()
    

# --- GESTION DE L'AUTHENTIFICATION ---
# Si 'user' n'est pas dans la session, afficher les pages de connexion/inscription.
if 'user' not in st.session_state or 'role' not in st.session_state:
    
    st.title("🔐 Connexion et Inscription")
    
    tab1, tab2 = st.tabs(["Se connecter", "S'inscrire"])
    
    with tab1:
        st.subheader("Accédez à votre espace")
        with st.form("login_form"):
            email_log = st.text_input("Email de connexion")
            pass_log = st.text_input("Mot de passe", type="password")
            submitted_log = st.form_submit_button("Se connecter")
            
            if submitted_log:
                # Appelle la fonction login de users.py
                login(email_log, pass_log, db)

    with tab2:
        st.subheader("Créez un nouveau compte")
        with st.form("register_form"):
            email_reg = st.text_input("Email d'inscription")
            pass_reg = st.text_input("Mot de passe (min 6 car.)", type="password")
            submitted_reg = st.form_submit_button("S'inscrire")
            
            if submitted_reg:
                if len(pass_reg) < 6:
                    st.error("Le mot de passe doit contenir au moins 6 caractères.")
                else:
                    # Appelle la fonction register de users.py
                    register(email_reg, pass_reg, db)

    # Arrête l'exécution si l'utilisateur n'est pas connecté
    st.stop()

else:
    # --- L'UTILISATEUR EST CONNECTÉ ---
    
    # Barre latérale avec infos utilisateur et déconnexion
    with st.sidebar:
        st.success(f"Connecté : {st.session_state['user']} (UID: {st.session_state['uid']})")
        # Le formulaire entry_form est dans forms.py
        entry = entry_form() 
        if entry:
            # Collection personnalisée par UID pour isoler les données
            collection_name = f"entries_{st.session_state['uid']}"
            if db.add_entry(collection_name, entry):
                st.success("Entrée ajoutée avec succès !")
                st.rerun() 
        
        st.markdown("---")
        logout() # Le bouton de déconnexion est dans users.py

    # --- TABLEAU DE BORD PRINCIPAL ---
    st.header("✨ Tableau de Bord de Gestion Budgétaire")

    collection_name = f"entries_{st.session_state['uid']}"
    entries = db.get_entries(collection_name)
    
    df = prepare_data(entries) # analysis.py

    if not df.empty:
        
        # 1. KPI (Indicateurs Clés)
        st.subheader("📊 Indicateurs Clés")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_profit = df['profit'].sum()
            st.metric("Profit Total", f"{total_profit:,.2f} €")

        with col2:
            avg_marge = df['marge'].mean()
            st.metric("Marge Moyenne", f"{avg_marge:.2f} %")
        
        with col3:
            forecast = forecast_prophet(df) # analysis.py
            if forecast is not None:
                st.metric("Prévision Profit (Mois prochain)", f"{forecast:,.2f} €")
            else:
                st.info("Pas assez de données pour la prévision.")

        # 2. Graphiques Interactifs (plots.py)
        st.markdown("---")
        st.subheader("📈 Visualisation")
        
        col_graph1, col_graph2 = st.columns(2)
        with col_graph1:
            st.plotly_chart(plot_revenue_expense(df), use_container_width=True)
        with col_graph2:
            st.plotly_chart(plot_profit_margin(df), use_container_width=True)

        # 3. Alertes Automatiques (utils.py)
        alert_expense(df) 

        # 4. Données Brutes
        st.markdown("---")
        st.subheader("📑 Historique des Transactions")
        st.dataframe(df.sort_index(ascending=False), use_container_width=True)
        
        # 5. Export (utils.py)
        st.subheader("📤 Exporter")
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            export_csv(df)
        with col_exp2:
            export_pdf(df)
            
    else:
        st.info("Ajoutez des entrées dans la barre latérale pour commencer à visualiser vos données.")