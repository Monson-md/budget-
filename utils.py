import streamlit as st
import base64
from io import BytesIO
import pandas as pd

def export_csv(df):
    """Bouton d'exportation CSV."""
    csv = df.to_csv(index=True, encoding='utf-8')
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="budget_export.csv">📥 Télécharger les données en CSV</a>'
    st.markdown(href, unsafe_allow_html=True)

def export_pdf(df):
    """Bouton d'exportation PDF (Simulation, nécessite des librairies complexes en réalité)."""
    
    # Pour Streamlit, on ne fait qu'une simulation simple d'export PDF, 
    # car la génération PDF nécessite des packages comme ReportLab ou FPDF, 
    # qui complexifieraient l'environnement DevContainer.
    
    buffer = BytesIO()
    # On écrit une version simple du CSV dans le buffer pour la démo
    df.to_csv(buffer, index=False)
    
    st.download_button(
        label="📄 Simuler l'Exportation PDF",
        data=buffer.getvalue(),
        file_name="budget_report_simule.pdf",
        mime="application/pdf"
    )

def alert_expense(df):
    """Affiche une alerte si une dépense importante a été enregistrée récemment."""
    df_expenses = df[df['type'] == 'Dépense']
    if df_expenses.empty:
        return
        
    recent_high_expense = df_expenses[df_expenses['amount'] > 500].sort_index(ascending=False).head(1)
    
    if not recent_high_expense.empty:
        row = recent_high_expense.iloc[0]
        st.sidebar.warning(f"🚨 Alerte Dépense Importante:\n{row['amount']:,.2f} € pour '{row['category']}' le {row.name.strftime('%Y-%m-%d')}.")