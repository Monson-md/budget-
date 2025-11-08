import streamlit as st
from db_client import DBClient
from forms import entry_form
from analysis import prepare_data, forecast_prophet
from plots import plot_revenue_expense, plot_profit_margin
from utils import export_csv, export_pdf, alert_expense
from users import login, logout
import pandas as pd

# Configuration de la page Streamlit
st.set_page_config(
    page_title="Gestion Budgétaire Finale", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- AUTHENTIFICATION ---
if 'user' not in st.session_state or 'role' not in st.session_state:
    login()
    st.info("Veuillez vous connecter pour accéder au tableau de bord.")
    st.stop() # Arrête l'exécution si non connecté
else:
    st.sidebar.success(f"Connecté : {st.session_state['user']} (Rôle: {st.session_state['role']})")
    logout() # Ajoute le bouton de déconnexion

# --- INITIALISATION ---
# Utilise un singleton DBClient pour toute l'application
if 'db' not in st.session_state:
    st.session_state['db'] = DBClient()
db = st.session_state['db']

# --- FORMULAIRE ET AJOUT D'ENTRÉE ---
entry = entry_form()
if entry:
    if db.add_entry("budget_entries", entry):
        st.sidebar.success("Entrée ajoutée avec succès !")
        st.rerun() # Rafraîchir pour voir la nouvelle donnée

# --- PRÉPARATION DES DONNÉES ---
entries = db.get_entries("budget_entries")
df = prepare_data(entries)

# --- TABLEAU DE BORD PRINCIPAL ---
st.header("✨ Tableau de Bord de Gestion Budgétaire")

if not df.empty:
    
    # 1. KPI (Key Performance Indicators)
    st.subheader("📊 Indicateurs Clés de Performance (KPI)")
    
    col_profit, col_marge, col_forecast = st.columns(3)
    
    # Profit Total
    with col_profit:
        total_profit = df['profit'].sum()
        st.metric("Profit Total", f"{total_profit:,.2f} €", delta=f"Base de {len(df)} entrées")

    # Marge Moyenne
    with col_marge:
        avg_marge = df['marge'].mean()
        st.metric("Marge Moyenne", f"{avg_marge:.2f} %")
    
    # Prévisions
    with col_forecast:
        forecast = forecast_prophet(df)
        if forecast is not None:
            st.metric("Prévision Profit Prochain Mois", f"{forecast:,.2f} €")
        else:
            st.info("Ajoutez plus de données pour la prévision.")

    # 2. Graphiques
    st.markdown("---")
    st.subheader("📈 Visualisation des Tendances")
    
    st.plotly_chart(plot_revenue_expense(df), use_container_width=True)
    st.plotly_chart(plot_profit_margin(df), use_container_width=True)

    # 3. Alertes
    alert_expense(df) # Appelle la fonction d'alerte sur la dernière entrée

    # 4. Données brutes et OCR
    st.markdown("---")
    st.subheader("📑 Justificatifs et Données Brutes")

    # Affichage du texte OCR
    ocr_data = df[df['justificatif_ocr'] != ""]
    if not ocr_data.empty:
        st.markdown("**Texte extrait par l'OCR :**")
        for idx, row in ocr_data.tail(5).iterrows(): # Affiche les 5 dernières pour la clarté
            st.code(f"[{idx.date()} - {row['category']}] : {row['justificatif_ocr']}", language="text")
    
    # Affichage du tableau de données brutes
    st.dataframe(df.style.format(precision=2), use_container_width=True)

    # 5. Export
    st.markdown("---")
    st.subheader("📤 Options d'Export")
    col_csv, col_pdf = st.columns(2)
    with col_csv:
        export_csv(df)
    with col_pdf:
        export_pdf(df)
        
else:
    st.info("Aucune donnée budgétaire n'est encore enregistrée. Utilisez le panneau latéral pour ajouter une première entrée.")