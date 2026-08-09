import streamlit as st
import pandas as pd
import io
from currency import CURRENCY_SYMBOLS, DEFAULT_ALERT_THRESHOLDS

# Colonnes de traçabilité du taux de change, ajoutées aux transactions à
# partir de ce changement. Les transactions créées avant ne les ont pas.
EXCHANGE_RATE_TRACE_COLUMNS = ["exchange_rate", "exchange_rate_source", "exchange_rate_date"]

def with_nd_placeholders(df, columns):
    """Copie de df où les valeurs manquantes des colonnes indiquées
    affichent "n/d" plutôt qu'une cellule vide/NaN. Sert à afficher/exporter
    proprement les anciennes transactions qui n'ont pas ces colonnes, sans
    migration de données."""
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = "n/d"
        else:
            df[col] = df[col].apply(lambda v: "n/d" if pd.isna(v) else v)
    return df

def export_csv(df, base_currency="XOF"):
    """Bouton d'exportation CSV natif Streamlit (plus rapide)."""
    if df.empty:
        st.warning("Aucune donnée à exporter en CSV.")
        return

    df_export = with_nd_placeholders(df, EXCHANGE_RATE_TRACE_COLUMNS)
    df_export = df_export.rename(columns={
        "amount": f"amount_{base_currency}",
        "profit": f"profit_{base_currency}",
    })
    csv = df_export.to_csv(index=True).encode('utf-8')
    st.download_button(
        label="📥 Télécharger l'historique (CSV)",
        data=csv,
        file_name="mon_budget_pro.csv",
        mime="text/csv",
        use_container_width=True
    )

def export_excel(df, base_currency="XOF"):  # RENOMMÉ : Plus logique que export_pdf
    """Exportation au format Excel sans erreur de fuseau horaire."""
    if df.empty:
        st.warning("Aucune donnée à exporter en Excel.")
        return

    output = io.BytesIO()

    # CORRECTION CRITIQUE : Copie du DataFrame et retrait des timezones
    df_clean = with_nd_placeholders(df, EXCHANGE_RATE_TRACE_COLUMNS)
    if isinstance(df_clean.index, pd.DatetimeIndex):
        df_clean.index = df_clean.index.tz_localize(None)

    # Nettoyage des colonnes contenant des dates si nécessaire
    for col in df_clean.columns:
        if pd.api.types.is_datetime64_any_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].dt.tz_localize(None)

    # Les colonnes montants portent le code de la devise de référence pour
    # que le rapport ne laisse jamais penser qu'il est exprimé en EUR.
    df_clean = df_clean.rename(columns={
        "amount": f"amount_{base_currency}",
        "profit": f"profit_{base_currency}",
    })

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_clean.to_excel(writer, index=True, sheet_name='Transactions')

    st.download_button(
        label="📄 Exporter pour Comptable (Excel)",
        data=output.getvalue(),
        file_name="rapport_finance.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

def alert_expense(df, threshold=None, base_currency="XOF"):
    """Système d'alerte intelligente sur les dépenses atypiques.

    threshold : seuil configurable par l'utilisateur ; si absent, on retombe
    sur un seuil par défaut adapté à la devise de référence.
    """
    df_expenses = df[df['type'] == 'Dépense']
    if df_expenses.empty:
        return

    if threshold is None:
        threshold = DEFAULT_ALERT_THRESHOLDS.get(base_currency, 500)
    symbole = CURRENCY_SYMBOLS.get(base_currency, base_currency)

    recent_high_expense = df_expenses[df_expenses['amount'] > threshold].sort_index(ascending=False).head(1)

    if not recent_high_expense.empty:
        row = recent_high_expense.iloc[0]

        # AJOUT SÉCURITÉ DEVISE : On vérifie si les colonnes de la devise originale existent
        if 'amount_original' in row and 'currency_original' in row:
            montant_txt = f"{row['amount_original']:,} {row['currency_original']} (soit {row['amount']:.2f} {symbole})"
        else:
            montant_txt = f"{row['amount']:.2f} {symbole}"

        st.toast(f"⚠️ Dépense élevée détectée : {montant_txt} en {row['category']}", icon="🚨")