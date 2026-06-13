import streamlit as st
import pandas as pd
import io

def export_csv(df):
    """Bouton d'exportation CSV natif Streamlit (plus rapide)."""
    if df.empty:
        st.warning("Aucune donnée à exporter en CSV.")
        return
        
    csv = df.to_csv(index=True).encode('utf-8')
    st.download_button(
        label="📥 Télécharger l'historique (CSV)",
        data=csv,
        file_name="mon_budget_pro.csv",
        mime="text/csv",
        use_container_width=True
    )

def export_excel(df):  # RENOMMÉ : Plus logique que export_pdf
    """Exportation au format Excel sans erreur de fuseau horaire."""
    if df.empty:
        st.warning("Aucune donnée à exporter en Excel.")
        return

    output = io.BytesIO()
    
    # CORRECTION CRITIQUE : Copie du DataFrame et retrait des timezones
    df_clean = df.copy()
    if isinstance(df_clean.index, pd.DatetimeIndex):
        df_clean.index = df_clean.index.tz_localize(None)
    
    # Nettoyage des colonnes contenant des dates si nécessaire
    for col in df_clean.columns:
        if pd.api.types.is_datetime64_any_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].dt.tz_localize(None)

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_clean.to_excel(writer, index=True, sheet_name='Transactions')
    
    st.download_button(
        label="📄 Exporter pour Comptable (Excel)",
        data=output.getvalue(),
        file_name="rapport_finance.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

def alert_expense(df):
    """Système d'alerte intelligente sur les dépenses atypiques."""
    df_expenses = df[df['type'] == 'Dépense']
    if df_expenses.empty:
        return
        
    # Seuil d'alerte fixé à 500 €
    seuil = 500
    recent_high_expense = df_expenses[df_expenses['amount'] > seuil].sort_index(ascending=False).head(1)
    
    if not recent_high_expense.empty:
        row = recent_high_expense.iloc[0]
        
        # AJOUT SÉCURITÉ DEVISE : On vérifie si les colonnes de la devise originale existent
        if 'amount_original' in row and 'currency_original' in row:
            montant_txt = f"{row['amount_original']:,} {row['currency_original']} (soit {row['amount']:.2f} €)"
        else:
            montant_txt = f"{row['amount']:.2f} €"
            
        st.toast(f"⚠️ Dépense élevée détectée : {montant_txt} en {row['category']}", icon="🚨")