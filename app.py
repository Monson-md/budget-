import streamlit as st
import pandas as pd
from temp_db_client import DBClient 
from forms import entry_form
from analysis import prepare_data, forecast_prophet
from plots import plot_revenue_expense, plot_profit_margin
# CORRECTION 1 : Importation de export_excel à la place de export_pdf
from utils import export_csv, export_excel, alert_expense 
from users import login, register, logout 

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="ProBudget AI - Dashboard", 
    page_icon="💰",
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- STYLE CSS PERSONNALISÉ ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #007bff; padding: 15px; border-radius: 10px; border: 1px solid #e6e9ef; }
    </style>
    """, unsafe_allow_html=True)

# --- INITIALISATION DE LA DB ---
if 'db' not in st.session_state:
    try:
        st.session_state['db'] = DBClient()
    except Exception as e:
        st.error(f"Erreur d'initialisation de la base de données : {e}")
        st.stop()
db = st.session_state['db']

# --- LOGIQUE D'ACCÈS (NON CONNECTÉ) ---
if 'user' not in st.session_state:
    # On cache le menu latéral si non connecté pour la sécurité
    st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>", unsafe_allow_html=True)
    
    st.title("🚀 Bienvenue sur ProBudget AI")
    st.info("Gerez vos finances avec la puissance de l'IA.")
    
    tab1, tab2 = st.tabs(["🔒 Connexion", "📝 Créer un compte"])
    
    with tab1:
        with st.form("login_form"):
            email_log = st.text_input("Email")
            pass_log = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Se connecter", use_container_width=True):
                login(email_log, pass_log, db)

    with tab2:
        with st.form("register_form"):
            email_reg = st.text_input("Email professionnel ou personnel")
            pass_reg = st.text_input("Mot de passe (sécure)", type="password")
            if st.form_submit_button("Créer mon compte", use_container_width=True):
                register(email_reg, pass_reg, db)
    st.stop()
    
# --- LOGIQUE D'ACCÈS (UTILISATEUR CONNECTÉ) ---
else:
    # Barre latérale globale de navigation
    with st.sidebar:
        st.title("Menu Principal")
        st.write(f"Connecté en tant que : **{st.session_state['user']}**")
        page = st.radio("Aller vers :", ["📊 Tableau de Bord", "🚀 Investissements"])
        st.markdown("---")
        logout()

    # --- SÉLECTION DES PAGES ---
    if page == "📊 Tableau de Bord":
        st.title("📊 Tableau de Bord Budgétaire")
        
        # Barre latérale de saisie (spécifique au budget)
        with st.sidebar:
            st.subheader("➕ Nouvelle Opération")
            entry = entry_form() 
            if entry:
                collection_name = f"entries_{st.session_state['uid']}"
                if db.add_entry(collection_name, entry):
                    st.success("Opération enregistrée avec succès !")
                    # Utilisation d'un rafraîchissement contrôlé pour éviter les boucles OCR
                    st.toast("Données synchronisées avec Firebase", icon="🔄")
                    st.rerun() 
        
        # Chargement et affichage des données du budget
        collection_name = f"entries_{st.session_state['uid']}"
        entries = db.get_entries(collection_name)
        df = prepare_data(entries)

        if not df.empty:
            # 1. Indicateurs Clés
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Profit Total (Pivot EUR)", f"{df['profit'].sum():,.2f} €", delta=None)
            with col2:
                # Éviter l'affichage de 'nan %' s'il n'y a pas encore assez de données de revenus
                marge_moyenne = df['marge'].mean()
                marge_txt = f"{marge_moyenne:.1f} %" if not pd.isna(marge_moyenne) else "0.0 %"
                st.metric("Marge Moyenne", marge_txt)
            with col3:
                forecast = forecast_prophet(df)
                val = f"{forecast:,.2f} €" if forecast else "Calcul..."
                st.metric("Prévision IA (M+1)", val)

            # 2. Graphiques
            st.subheader("📈 Analyses Graphiques")
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(plot_revenue_expense(df), use_container_width=True)
            with c2:
                st.plotly_chart(plot_profit_margin(df), use_container_width=True)

            # 3. Alertes et Historique
            alert_expense(df) 
            
            with st.expander("📂 Voir l'historique complet des transactions"):
                # Tri de l'affichage par index décroissant pour voir les plus récents en premier
                st.dataframe(df.sort_index(ascending=False), use_container_width=True)
            
            # 4. Modules d'Export
            st.markdown("---")
            st.subheader("📥 Rapports")
            exp1, exp2 = st.columns(2)
            with exp1:
                export_csv(df)
            with exp2:
                # CORRECTION 2 : Appel du bon nom de la fonction Excel
                export_excel(df)
                
        else:
            st.warning("👋 Bienvenue ! Commencez par ajouter votre première transaction dans le menu à gauche.")  

    elif page == "🚀 Investissements":
        # Importation dynamique du module de la Phase 2
        try:
            from investments import investment_dashboard
            investment_dashboard(db, st.session_state['uid'])
        except ImportError:
            st.error("Le fichier 'investments.py' est manquant ou contient une erreur de syntaxe.")