import streamlit as st
from datetime import date

def entry_form():
    """
    Formulaire pour ajouter une nouvelle entrée de revenu ou de dépense.
    """
    st.sidebar.header("➕ Ajouter une Entrée")

    with st.sidebar.form("entry_form"):
        type_entry = st.radio("Type d'entrée", ["Revenu", "Dépense"])
        
        montant = st.number_input("Montant (€)", min_value=0.01, format="%.2f")
        
        # Le type détermine les catégories
        if type_entry == "Revenu":
            categories = ["Salaire", "Investissement", "Cadeau", "Autre Revenu"]
            default_cat = categories[0]
        else:
            categories = ["Loyer", "Nourriture", "Transport", "Loisirs", "Factures", "Autre Dépense"]
            default_cat = categories[0]

        categorie = st.selectbox("Catégorie", categories, index=categories.index(default_cat))
        
        date_entry = st.date_input("Date", date.today())
        
        description = st.text_area("Description (Optionnel)")
        
        # Placeholder pour le fichier (OCR)
        uploaded_file = st.file_uploader("Joindre un justificatif (reçu/facture)", type=['png', 'jpg', 'jpeg'])

        submitted = st.form_submit_button("Enregistrer l'Entrée")
        
        if submitted:
            # Ici, on simulerait l'OCR ou l'on passerait le fichier au serveur
            ocr_text = f"Fichier: {uploaded_file.name}" if uploaded_file else ""
            
            return {
                "type": type_entry,
                "amount": montant,
                "category": categorie,
                "date": date_entry.isoformat(),
                "description": description,
                "justificatif_ocr": ocr_text,
                "timestamp": date.today().isoformat()
            }
        return None