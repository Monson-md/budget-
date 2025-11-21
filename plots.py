import plotly.express as px
import pandas as pd

def plot_revenue_expense(df):
    """Trace les revenus et les dépenses mensuelles."""
    # Agrégation mensuelle
    monthly_summary = df.resample('M').agg(
        Revenu=('amount', lambda x: x[df.loc[x.index, 'type'] == 'Revenu'].sum()),
        Dépense=('amount', lambda x: x[df.loc[x.index, 'type'] == 'Dépense'].sum())
    ).fillna(0).reset_index()
    
    monthly_summary['month'] = monthly_summary['date'].dt.strftime('%Y-%m')

    fig = px.bar(
        monthly_summary,
        x='month',
        y=['Revenu', 'Dépense'],
        title='Revenus vs Dépenses Mensuelles',
        labels={'value': 'Montant (€)', 'month': 'Mois'},
        barmode='group'
    )
    fig.update_layout(legend_title_text='Type', yaxis_title='Montant (€)')
    return fig

def plot_profit_margin(df):
    """Trace la marge bénéficiaire mensuelle (basé sur l'agrégation dans analysis.py)."""
    
    # Agrégation mensuelle (pour avoir la colonne 'marge')
    monthly_data = df.resample('M').agg(
        Revenu=('amount', lambda x: x[df.loc[x.index, 'type'] == 'Revenu'].sum()),
        Dépense=('amount', lambda x: x[df.loc[x.index, 'type'] == 'Dépense'].sum())
    ).fillna(0)
    
    monthly_data['marge'] = ((monthly_data['Revenu'] - monthly_data['Dépense']) / monthly_data['Revenu']) * 100
    monthly_data.loc[monthly_data['Revenu'] == 0, 'marge'] = 0
    monthly_data = monthly_data.reset_index()
    monthly_data['month'] = monthly_data['date'].dt.strftime('%Y-%m')

    fig = px.line(
        monthly_data,
        x='month',
        y='marge',
        title='Marge Bénéficiaire Mensuelle (%)',
        labels={'marge': 'Marge (%)', 'month': 'Mois'},
        markers=True
    )
    fig.update_traces(line_color='#2ecc71')
    fig.update_layout(yaxis_range=[-100, 100]) # Marge entre -100% et 100%
    return fig