import streamlit as st
import pandas as pd
import extra_streamlit_components as stx
from temp_db_client import DBClient
from forms import entry_form
from analysis import prepare_data, forecast_prophet, PROPHET_AVAILABLE
from plots import plot_revenue_expense, plot_profit_margin
# CORRECTION 1 : Importation de export_excel à la place de export_pdf
from utils import export_csv, export_excel, alert_expense
from users import login, register, logout, request_password_reset, reset_password, try_remember_me_login
from currency import CURRENCY_SYMBOLS, DEFAULT_ALERT_THRESHOLDS

# --- CONFIGURATION DE LA PAGE ---
# Doit rester la toute première commande Streamlit du script : on ne crée le
# CookieManager (qui rend un composant) qu'après.
st.set_page_config(
    page_title="ProBudget AI - Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Un seul CookieManager par run de script (composant custom réutilisé pour
# lire/poser/supprimer le cookie "rester connecté").
cookie_manager = stx.CookieManager(key="cookie_manager")

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
    except Exception:
        # Pas de détail brut d'exception : il peut contenir des fragments de la clé Firebase.
        st.error("Erreur d'initialisation de la base de données.")
        st.stop()
db = st.session_state['db']

# --- RECONNEXION AUTOMATIQUE ("RESTER CONNECTÉ") ---
# Survit aux rechargements de page (retape d'URL, ou rechargement forcé de
# l'onglet mobile après ouverture de l'appareil photo/sélecteur de fichiers)
# qui vident st.session_state.
if 'user' not in st.session_state:
    try_remember_me_login(db, cookie_manager)

# --- LOGIQUE D'ACCÈS (NON CONNECTÉ) ---
if 'user' not in st.session_state:
    # On cache le menu latéral si non connecté pour la sécurité
    st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;}</style>", unsafe_allow_html=True)
    
    st.title("🚀 Bienvenue sur ProBudget AI")
    st.info("Gerez vos finances avec la puissance de l'IA.")
    
    tab1, tab2, tab3 = st.tabs(["🔒 Connexion", "📝 Créer un compte", "🔑 Mot de passe oublié"])

    with tab1:
        with st.form("login_form"):
            email_log = st.text_input("Email")
            pass_log = st.text_input("Mot de passe", type="password")
            remember_me = st.checkbox("Rester connecté sur cet appareil", value=True)
            if st.form_submit_button("Se connecter", use_container_width=True):
                login(email_log, pass_log, db, cookie_manager=cookie_manager, remember_me=remember_me)

    with tab2:
        with st.form("register_form"):
            email_reg = st.text_input("Email professionnel ou personnel")
            pass_reg = st.text_input("Mot de passe (sécure)", type="password")
            devise_reg = st.selectbox("Devise de référence", list(CURRENCY_SYMBOLS.keys()))
            if st.form_submit_button("Créer mon compte", use_container_width=True):
                register(email_reg, pass_reg, db, base_currency=devise_reg)

    with tab3:
        st.caption(
            "Aucun service d'email n'est configuré pour l'instant : le code de "
            "réinitialisation doit être récupéré manuellement (console Firestore) "
            "et transmis à l'utilisateur par l'administrateur."
        )
        with st.form("reset_request_form"):
            st.markdown("##### 1. Demander un code de réinitialisation")
            email_reset_req = st.text_input("Email du compte")
            if st.form_submit_button("Demander un code", use_container_width=True):
                request_password_reset(email_reset_req, db)

        with st.form("reset_confirm_form"):
            st.markdown("##### 2. Utiliser le code reçu")
            email_reset = st.text_input("Email", key="reset_email")
            token_reset = st.text_input("Code de réinitialisation")
            new_pass_reset = st.text_input("Nouveau mot de passe", type="password")
            if st.form_submit_button("Réinitialiser le mot de passe", use_container_width=True):
                reset_password(email_reset, token_reset, new_pass_reset, db)
    st.stop()
    
# --- LOGIQUE D'ACCÈS (UTILISATEUR CONNECTÉ) ---
else:
    base_currency = st.session_state.get('base_currency', 'XOF')
    currency_symbol = CURRENCY_SYMBOLS.get(base_currency, base_currency)

    # Barre latérale globale de navigation
    with st.sidebar:
        st.title("Menu Principal")
        st.write(f"Connecté en tant que : **{st.session_state['user']}**")
        page = st.radio("Aller vers :", ["📊 Tableau de Bord", "🚀 Investissements"])

        with st.expander("⚙️ Paramètres du profil"):
            currency_options = list(CURRENCY_SYMBOLS.keys())
            new_currency = st.selectbox(
                "Devise de référence",
                currency_options,
                index=currency_options.index(base_currency) if base_currency in currency_options else 0,
                key="settings_currency"
            )
            current_threshold = st.session_state.get(
                'alert_threshold', DEFAULT_ALERT_THRESHOLDS.get(base_currency, 500)
            )
            new_threshold = st.number_input(
                f"Seuil d'alerte dépense élevée ({CURRENCY_SYMBOLS.get(new_currency, new_currency)})",
                min_value=0.0, value=float(current_threshold), step=10.0, key="settings_threshold"
            )
            if st.button("Enregistrer les paramètres", use_container_width=True):
                if db.update_user(st.session_state['user'], {
                    "base_currency": new_currency,
                    "alert_threshold": new_threshold,
                }):
                    st.session_state['base_currency'] = new_currency
                    st.session_state['alert_threshold'] = new_threshold
                    st.success("Paramètres mis à jour.")
                    st.rerun()

        st.markdown("---")
        logout(db, cookie_manager)

        st.markdown("---")
        st.subheader("☕ Soutenir le projet")
        if st.button("Faire un don", key="donate_btn", use_container_width=True):
            db.log_donation_click(st.session_state.get('user', ''))
            st.success(
                "Merci ! Envoie ton soutien via Orange Money / Wave au "
                "+223 71302389. ⚠️ Ceci n'est pas un paiement automatique : "
                "c'est juste le numéro à utiliser manuellement dans ton app "
                "Orange Money ou Wave."
            )

    # --- SÉLECTION DES PAGES ---
    if page == "📊 Tableau de Bord":
        st.title("📊 Tableau de Bord Budgétaire")
        
        # Barre latérale de saisie (spécifique au budget)
        with st.sidebar:
            st.subheader("➕ Nouvelle Opération")
            entry = entry_form(base_currency)
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
            # La carte "Prévision IA" n'apparaît que si Prophet est disponible ;
            # sinon le reste du tableau de bord continue de fonctionner normalement.
            cols = st.columns(3) if PROPHET_AVAILABLE else st.columns(2)
            col1, col2 = cols[0], cols[1]
            with col1:
                st.metric(f"Profit Total (Pivot {base_currency})", f"{df['profit'].sum():,.2f} {currency_symbol}", delta=None)
            with col2:
                # Éviter l'affichage de 'nan %' s'il n'y a pas encore assez de données de revenus
                marge_moyenne = df['marge'].mean()
                marge_txt = f"{marge_moyenne:.1f} %" if not pd.isna(marge_moyenne) else "0.0 %"
                st.metric("Marge Moyenne", marge_txt)

            if PROPHET_AVAILABLE:
                with cols[2]:
                    with st.spinner("Calcul de la prévision IA..."):
                        forecast = forecast_prophet(df)
                    if forecast is not None:
                        st.metric("Prévision IA (M+1)", f"{forecast:,.2f} {currency_symbol}")
                    else:
                        st.metric("Prévision IA (M+1)", "Indisponible")

            # 2. Graphiques
            st.subheader("📈 Analyses Graphiques")
            c1, c2 = st.columns(2)
            with c1:
                st.plotly_chart(plot_revenue_expense(df, base_currency), use_container_width=True)
            with c2:
                st.plotly_chart(plot_profit_margin(df), use_container_width=True)

            # 3. Alertes et Historique
            alert_expense(df, st.session_state.get('alert_threshold'), base_currency)
            
            with st.expander("📂 Voir l'historique complet des transactions"):
                # Tri de l'affichage par index décroissant pour voir les plus récents en premier
                st.dataframe(df.sort_index(ascending=False), use_container_width=True)
            
            # 4. Modules d'Export
            st.markdown("---")
            st.subheader("📥 Rapports")
            exp1, exp2 = st.columns(2)
            with exp1:
                export_csv(df, base_currency)
            with exp2:
                # CORRECTION 2 : Appel du bon nom de la fonction Excel
                export_excel(df, base_currency)
                
        else:
            st.warning("👋 Bienvenue ! Commencez par ajouter votre première transaction dans le menu à gauche.")  

    elif page == "🚀 Investissements":
        # Importation dynamique du module de la Phase 2
        try:
            from investments import investment_dashboard
            investment_dashboard(db, st.session_state['uid'], base_currency)
        except Exception:
            # On capture toute exception (pas seulement ImportError) : une
            # erreur de syntaxe ou une erreur runtime dans investments.py ne
            # doit jamais afficher de traceback brut à l'écran.
            st.error("Le module 'Investissements' est indisponible pour le moment (fichier manquant ou en erreur).")