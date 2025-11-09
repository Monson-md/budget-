import pytesseract
from PIL import Image
from forex_python.converter import CurrencyRates
import streamlit as st
import pandas as pd
import pdfkit
import io
import os

# Configuration pour le chemin Tesseract si nécessaire
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def ocr_receipt(file):
    if file:
        try:
            img = Image.open(file)
            # Utilise 'fra' pour le français. Changez à 'eng' ou autre si besoin.
            text = pytesseract.image_to_string(img, lang='fra')
            return text
        except Exception as e:
            # Afficher l'erreur pour aider au debugging (souvent lié à Tesseract non installé)
            st.error(f"Erreur OCR : Assurez-vous que Tesseract est installé. Détail: {e}")
    return ""

def convert_currency(amount, from_currency="USD", to_currency="EUR"):
    if from_currency == to_currency:
        return amount
    try:
        c = CurrencyRates()
        # Récupère le taux du jour
        rate = c.get_rate(from_currency, to_currency)
        return round(amount * rate, 2)
    except Exception as e:
        st.error(f"Erreur conversion devises pour {from_currency}: {e}. Montant non converti.")
        return amount

def alert_expense(df, seuil=10000):
    """Affiche une alerte si la dernière dépense dépasse un seuil."""
    if not df.empty and 'depense' in df.columns:
        last_expense = df['depense'].iloc[-1]
        if last_expense > seuil:
            st.warning(f"🚨 ALERTE DÉPENSE ÉLEVÉE : {last_expense:,.2f} €")

def export_csv(df):
    # Créer un objet io.StringIO pour Streamlit download button
    csv = df.to_csv(index=True).encode('utf-8')
    st.download_button(
        label="Télécharger en CSV",
        data=csv,
        file_name='export_budget.csv',
        mime='text/csv',
    )

# Dans utils.py



# utils.py

import pdfkit # Assurez-vous que pdfkit est importé
# ... autres imports ...

# =======================================================
# 1. DÉFINITION GLOBALE DE LA CONFIGURATION (CORRECTION)
# =======================================================
# Spécifiez le chemin d'accès à l'exécutable wkhtmltopdf.exe 
# (Ceci est nécessaire si la modification du PATH système ne fonctionne pas)
path_wkhtmltopdf = r'C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe'
config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

def export_csv(df):
    # ... votre code pour l'export CSV
    pass

def export_pdf(html_content, filename):
    try:
        # 2. Utilisation de la variable 'config' définie globalement
        pdfkit.from_string(html_content, filename, configuration=config) 
        
        # Le reste de la fonction
        with open(filename, "rb") as pdf_file:
            # ... votre code Streamlit pour le bouton de téléchargement
            pass
            
        return "PDF generated successfully"

    except Exception as e:
        # ...
        return f"Erreur PDF: {e}"