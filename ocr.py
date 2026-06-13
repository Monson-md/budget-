import streamlit as st
import pytesseract
from PIL import Image
import re

# Liaison avec le logiciel Tesseract que tu es en train d'installer
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def extract_amount_from_text(text):
    """
    Analyse le texte du ticket avec une Regex pour trouver le montant TOTAL.
    """
    # Cette formule cherche des mots clés comme TOTAL, NET, PRIX suivis d'un chiffre
    patterns = [
        r'(?:total|net|payer|montant|ttc)[\s\D]*([\d+[\.,]\d{2})',
        r'([\d+[\.,]\d{2})\s*(?:€|eur|xof|cfa)'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # On prend le dernier montant trouvé (souvent le total en bas du ticket)
            amount_str = matches[-1].replace(',', '.')
            try:
                return float(amount_str)
            except ValueError:
                continue
    return 0.0

def scan_receipt_dashboard():
    """Interface Streamlit pour scanner un ticket."""
    st.markdown("### 📸 Smart Scan : Analyseur de Reçus")
    st.info("Prenez une photo de votre ticket de caisse ou glissez-la ici. L'IA va remplir le montant automatiquement !")

    uploaded_file = st.file_uploader("Choisissez une image de ticket...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        # Affichage de l'image téléversée sur le côté
        col1, col2 = st.columns([1, 1])
        
        with col1:
            image = Image.open(uploaded_file)
            st.image(image, caption="Ticket téléversé", use_container_width=True)
            
        with col2:
            with st.spinner("🔍 Lecture du ticket en cours avec Tesseract..."):
                try:
                    # Extraction du texte en spécifiant le français et l'anglais
                    extracted_text = pytesseract.image_to_string(image, lang='fra+eng')
                    
                    st.success("🤖 Lecture terminée !")
                    
                    # Détection du montant automatique
                    detected_amount = extract_amount_from_text(extracted_text)
                    
                    # Formulaire pré-rempli pour l'utilisateur
                    st.markdown("#### 📝 Validation des données lues")
                    final_amount = st.number_input("Montant détecté (€)", value=float(detected_amount), step=0.01)
                    
                    # Petit aperçu du texte lu pour déboguer si besoin
                    with st.expander("📄 Voir le texte brut extrait du ticket"):
                        st.text(extracted_text)
                        
                    return final_amount
                    
                except Exception as e:
                    st.error(f"Erreur lors de la lecture OCR : {e}")
                    st.warning("Assurez-vous que l'installation de Tesseract est bien terminée.")
    return None