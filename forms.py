import streamlit as st
from datetime import date, datetime
import pytesseract
from PIL import Image
import re
import os
# IMPORTATION DU MODULE QUE TU AS CRÉÉ
from currency import get_exchange_rate_with_source

# Gestion automatique du chemin Tesseract (Local Windows vs Serveur Linux)
windows_tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.exists(windows_tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = windows_tesseract_path

# Taille max du texte OCR brut conservé en base, pour éviter de gonfler
# Firestore avec des tickets entiers à chaque transaction.
MAX_OCR_TEXT_LENGTH = 500

# Mots-clés qui, présents sur une ligne, disqualifient celle-ci comme montant
# total même si elle contient aussi "total" (ex: "Sous-total") ou un autre
# mot-clé de montant : ce sont des montants intermédiaires ou annexes, jamais
# le total réellement dû. Variantes non accentuées incluses pour tolérer les
# fautes d'OCR sur les accents.
EXCLUDED_AMOUNT_KEYWORDS = [
    'espèces', 'especes',
    'monnaie',
    'rendu',
    'reçu', 'recu',
    'sous-total', 'sous total',
    'tva',
    'acompte',
]

def _line_has_excluded_keyword(line):
    lower = line.lower()
    return any(keyword in lower for keyword in EXCLUDED_AMOUNT_KEYWORDS)

def extract_amount_from_text(text):
    """Analyse le texte du ticket pour trouver le montant total.

    Gère deux formats de montant :
    - FCFA/entier : "7 220", "1 101" (chiffres groupés par des espaces,
      sans décimales)
    - EUR/décimal : "12,34", "12.34" (virgule ou point suivi de 2 décimales)

    Sur les tickets à montants multiples (sous-total, TVA, total, espèces
    données, monnaie rendue...), seule une ligne contenant "total" ou
    "à payer" ET ne contenant aucun mot-clé de EXCLUDED_AMOUNT_KEYWORDS est
    retenue comme candidate ; s'il y en a plusieurs, la dernière du ticket
    l'emporte (le total final vient généralement après le sous-total).
    """
    if not text:
        return 0.0

    # Chiffres éventuellement groupés par des espaces (séparateur de
    # milliers FCFA), suivis en option d'une partie décimale (format EUR).
    number = r'(\d[\d\s]*\d|\d)(?:[.,](\d{2}))?'
    number_re = re.compile(number)

    def _parse_amount(int_part, dec_part):
        # Nettoyage des espaces (classiques et insécables) utilisés comme
        # séparateur de milliers, sans toucher à la décimale capturée
        # séparément dans dec_part.
        montant_str = int_part.replace(' ', '').replace('\xa0', '')
        if dec_part:
            montant_str += f'.{dec_part}'
        try:
            return float(montant_str)
        except ValueError:
            return None

    lines = text.splitlines()

    # 1. Priorité stricte : dernière ligne contenant "total" ou "à payer",
    # sans mot-clé exclu.
    total_keyword_re = re.compile(r'total|à\s*payer', re.IGNORECASE)
    last_total_amount = None
    for line in lines:
        if not total_keyword_re.search(line) or _line_has_excluded_keyword(line):
            continue
        match = number_re.search(line)
        if match:
            amount = _parse_amount(match.group(1), match.group(2))
            if amount is not None:
                last_total_amount = amount
    if last_total_amount is not None:
        return last_total_amount

    # 2. Repli : mots-clés de montant plus larges (net, montant, ttc), puis
    # montant directement suivi d'un symbole/code de devise. Toujours en
    # ignorant les lignes contenant un mot-clé exclu, et en gardant la
    # dernière occurrence trouvée dans le ticket.
    patterns = [
        r'(?:net|montant|ttc)[^\d\n]*' + number,
        number + r'\s*(?:€|eur|xof|cfa|fcfa)',
    ]
    for pattern in patterns:
        pattern_re = re.compile(pattern, re.IGNORECASE)
        last_amount = None
        for line in lines:
            if _line_has_excluded_keyword(line):
                continue
            for match in pattern_re.finditer(line):
                amount = _parse_amount(match.group(1), match.group(2))
                if amount is not None:
                    last_amount = amount
        if last_amount is not None:
            return last_amount

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
            # Conversion automatique vers la devise de référence du profil.
            # On garde aussi le taux, sa source (api/fallback) et la date de
            # conversion, pour pouvoir expliquer plus tard un montant converti.
            taux, taux_source = get_exchange_rate_with_source(devise, base_currency)
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
                "exchange_rate": taux,
                "exchange_rate_source": taux_source,
                "exchange_rate_date": datetime.now().isoformat(),
                "category": categorie,
                "date": date_entry.isoformat(),
                "description": description,
                "justificatif_name": file_name,
                "justificatif_raw_text": texte_stocke,
                "created_at": date.today().isoformat()
            }
    return None