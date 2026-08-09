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

# Taille max du texte OCR brut conservé en base, pour éviter de gonfler
# Firestore avec des tickets entiers à chaque transaction.
MAX_OCR_TEXT_LENGTH = 500

def extract_amount_from_text(text):
    """Analyse le texte du ticket pour trouver le montant total.

    Gère deux formats de montant :
    - FCFA/entier : "7 220", "1 101" (chiffres groupés par des espaces,
      sans décimales)
    - EUR/décimal : "12,34", "12.34" (virgule ou point suivi de 2 décimales)
    """
    if not text:
        return 0.0

    # Chiffres éventuellement groupés par des espaces (séparateur de
    # milliers FCFA), suivis en option d'une partie décimale (format EUR).
    number = r'(\d[\d\s]*\d|\d)(?:[.,](\d{2}))?'

    patterns = [
        # Priorité : montant situé juste après un mot-clé de total. Le
        # séparateur exclut explicitement les retours à la ligne pour ne
        # pas "sauter" sur une autre ligne du ticket (ex: la ligne TVA).
        r'(?:total|net|à\s*payer|payer|montant|ttc)[^\d\n]*' + number,
        # Repli : montant directement suivi d'un symbole/code de devise.
        number + r'\s*(?:€|eur|xof|cfa|fcfa)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            int_part, dec_part = matches[-1]
            # Nettoyage des espaces (classiques et insécables) utilisés
            # comme séparateur de milliers, sans toucher à la décimale
            # capturée séparément dans dec_part.
            montant_str = int_part.replace(' ', '').replace('\xa0', '')
            if dec_part:
                montant_str += f'.{dec_part}'
            try:
                return float(montant_str)
            except ValueError:
                continue
    return 0.0

def entry_form(base_currency="XOF"):
    """Formulaire de saisie avec détection OCR et conversion de devises.

    base_currency : devise de référence du profil utilisateur, utilisée comme
    devise pivot pour la conversion (au lieu d'EUR codé en dur).
    """
    st.sidebar.header("➕ Nouvelle Transaction")

    # 1. Zone de Scan (Hors du formulaire)
    st.sidebar.markdown("### 📸 Optionnel : Scanner un Ticket")
    uploaded_file = st.sidebar.file_uploader("Preuve d'achat (Image)", type=['png', 'jpg', 'jpeg'], key="ocr_uploader")
    keep_ocr_text = st.sidebar.checkbox(
        "Conserver le texte OCR brut du ticket (débogage)",
        value=False,
        key="keep_ocr_text",
        help="Désactivé par défaut pour ne pas gonfler la base avec le texte intégral de chaque ticket."
    )

    montant_initial = 0.01
    texte_brut_ticket = "Aucun scan effectué"

    # Devise affichée dans le message de succès du scan : on lit la sélection
    # déjà faite par l'utilisateur dans le formulaire (via sa clé de widget),
    # avec la devise de référence du profil comme valeur par défaut avant
    # tout choix explicite.
    devise_options = ["XOF", "EUR", "USD"]
    default_index = devise_options.index(base_currency) if base_currency in devise_options else 0
    devise_widget_key = "entry_form_devise"
    devise_affichage = st.session_state.get(devise_widget_key, base_currency)

    if uploaded_file is not None:
        with st.spinner("🔍 Lecture du ticket..."):
            try:
                image = Image.open(uploaded_file)
                extracted_text = pytesseract.image_to_string(image, lang='fra+eng')
                texte_brut_ticket = extracted_text

                detected_amount = extract_amount_from_text(extracted_text)
                if detected_amount > 0:
                    montant_initial = detected_amount
                    st.sidebar.success(f"🎯 Montant détecté : {detected_amount:.2f} {devise_affichage}")
                else:
                    st.sidebar.warning("Ticket lu, mais aucun montant détecté automatiquement.")
            except Exception:
                st.sidebar.error("Erreur lors de la lecture du ticket (OCR).")

    # 2. Le Formulaire de Saisie standard
    st.sidebar.markdown("### 📝 Détails de l'opération")
    with st.sidebar.form("entry_form", clear_on_submit=True):
        type_entry = st.radio("Nature", ["Revenu", "Dépense"], horizontal=True)

        # Sélection de la devise, avec la devise de référence du profil pré-sélectionnée
        devise = st.selectbox("Devise de saisie", devise_options, index=default_index, key=devise_widget_key)

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
            # Conversion automatique vers la devise de référence du profil
            taux = get_exchange_rate(devise, base_currency)
            montant_converti = round(montant_saisi * taux, 2)

            file_name = uploaded_file.name if uploaded_file else "Aucun justificatif"

            if not keep_ocr_text or texte_brut_ticket == "Aucun scan effectué":
                texte_stocke = texte_brut_ticket if texte_brut_ticket == "Aucun scan effectué" else "Non conservé (désactivé par l'utilisateur)"
            else:
                texte_stocke = texte_brut_ticket[:MAX_OCR_TEXT_LENGTH]

            return {
                "type": type_entry,
                "amount_original": montant_saisi,
                "currency_original": devise,
                "amount": montant_converti,
                "currency_pivot": base_currency,
                "category": categorie,
                "date": date_entry.isoformat(),
                "description": description,
                "justificatif_name": file_name,
                "justificatif_raw_text": texte_stocke,
                "created_at": date.today().isoformat()
            }
    return None