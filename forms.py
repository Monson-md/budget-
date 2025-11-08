import streamlit as st
from datetime import datetime
from utils import ocr_receipt, convert_currency

def entry_form():
    st.sidebar.header("➕ Nouvelle entrée")
    
    # Le formulaire est dans un conteneur pour éviter les soumissions accidentelles
    with st.sidebar.form("form_new_entry"):
        date = st.date_input("Date", datetime.now())
        category = st.selectbox("Catégorie", ["Ventes","Marketing","Salaires","Equipement","Autre"])
        
        # Saisie du montant et de la devise
        col1, col2 = st.columns(2)
        with col1:
            revenu = st.number_input("Revenu (Montant)", min_value=0.0, step=100.0, key="rev_input")
        with col2:
            depense = st.number_input("Dépense (Montant)", min_value=0.0, step=100.0, key="dep_input")
        
        currency = st.selectbox("Devise d'origine", ["EUR","USD","GBP","CAD","JPY"])
        
        note = st.text_area("Note / Description")
        justificatif = st.file_uploader("Joindre un reçu (image)", type=['png', 'jpg', 'jpeg'])
        
        submitted = st.form_submit_button("✅ Ajouter l'entrée")

        if submitted:
            # 1. Conversion des devises si nécessaire
            rev_eur = revenu
            dep_eur = depense
            if currency != "EUR":
                rev_eur = convert_currency(revenu, from_currency=currency, to_currency="EUR")
                dep_eur = convert_currency(depense, from_currency=currency, to_currency="EUR")
            
            # 2. Structure de l'entrée
            entry = {
                "date": date.strftime("%Y-%m-%d"),
                "category": category,
                "revenu": rev_eur,  # Stocké en EUR
                "depense": dep_eur, # Stocké en EUR
                "devise_originale": currency,
                "note": note,
            }

            # 3. Traitement OCR
            if justificatif:
                text = ocr_receipt(justificatif)
                entry["justificatif_ocr"] = text # Nouvelle clé pour le texte OCR
            else:
                entry["justificatif_ocr"] = ""

            return entry
    return None