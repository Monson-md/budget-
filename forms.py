import streamlit as st
from datetime import date
import pytesseract
from PIL import Image
import re
import os
# IMPORTATION DU MODULE QUE TU AS CRÉÉ
from currency import get_exchange_rate 

# Gestion automatique du chemin Tesseract (Local Windows vs Serveur Linux)
windows_tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(windows_tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = windows_tesseract_path

def extract_amount_from_text(text):
    """Analyse le texte du ticket pour trouver le montant total."""
    # CORRECTION DES REGEX : Formules nettoyées pour attraper parfaitement les prix
    patterns = [
        r'(?:total|net|payer|montant|ttc)[\s\D]*(\d+[\.,]\d{2})',
        r'(\d+[\.,]\d{2})\s*(?:€|eur|xof|cfa)'
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            amount_str = matches[-1].replace(',', '.')
            try:
                return float(amount_str)
            except ValueError:
                continue
    return 0.0

def entry_form():
    """Formulaire de saisie avec détection OCR et conversion de devises."""
    st.sidebar.header("➕ Nouvelle Transaction")

    # 1. Zone de Scan (Hors du formulaire)
    st.sidebar.markdown("### 📸 Optionnel : Scanner un Ticket")
    uploaded_file = st.sidebar.file_uploader("Preuve d'achat (Image)", type=['png', 'jpg', 'jpeg'], key="ocr_uploader")
    
    montant_initial = 0.01
    texte_brut_ticket = "Aucun scan effectué"

    if uploaded_file is not None:
        with st.spinner("🔍 Lecture du ticket..."):
            try:
                image = Image.open(uploaded_file)
                extracted_text = pytesseract.image_to_string(image, lang='fra+eng')
                texte_brut_ticket = extracted_text
                
                detected_amount = extract_amount_from_text(extracted_text)
                if detected_amount > 0:
                    montant_initial = detected_amount
                    st.sidebar.success(f"🎯 Montant détecté : {detected_amount:.2f} €")
                else:
                    st.sidebar.warning("Ticket lu, mais aucun montant détecté automatiquement.")
            except Exception as e:
                st.sidebar.error(f"Erreur OCR : {e}")

    # 2. Le Formulaire de Saisie standard
    st.sidebar.markdown("### 📝 Détails de l'opération")
    with st.sidebar.form("entry_form", clear_on_submit=True):
        type_entry = st.radio("Nature", ["Revenu", "Dépense"], horizontal=True)
        
        # Sélection de la devise
        devise = st.selectbox("Devise de saisie", ["EUR", "XOF", "USD"])
        
        # Le champ montant prend la valeur détectée par l'OCR si elle existe !
        montant_saisi = st.number_input(f"Montant en ({devise})", min_value=0.00, value=float(montant_initial), step=0.01, format="%.2f")
        
        if type_entry == "Revenu":
            categories = ["Salaire", "Business", "Investissement", "Cadeau", "Vente", "Autre"]
        else:
            categories = ["Loyer/Logement", "Alimentation", "Transport", "Loisirs", "Santé", "Abonnements", "Impôts", "Autre"]

        categorie = st.selectbox("Catégorie", categories)
        date_entry = st.date_input("Date de l'opération", date.today())
        description = st.text_input("Note / Description")

        submitted = st.form_submit_button("🚀 Enregistrer", use_container_width=True)
        
        if submitted:
            # Conversion automatique via ton fichier currency.py
            taux = get_exchange_rate(devise, "EUR")
            montant_en_eur = round(montant_saisi * taux, 2)
            
            file_name = uploaded_file.name if uploaded_file else "Aucun justificatif"
            
            return {
                "type": type_entry,
                "amount_original": montant_saisi,
                "currency_original": devise,
                "amount": montant_en_eur,
                "category": categorie,
                "date": date_entry.isoformat(),
                "description": description,
                "justificatif_name": file_name,
                "justificatif_raw_text": texte_brut_ticket,
                "created_at": date.today().isoformat()
            }
    return None