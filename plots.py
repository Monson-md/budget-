import plotly.express as px
import pandas as pd
from currency import CURRENCY_SYMBOLS

def plot_revenue_expense(df, base_currency="XOF"):
    """Trace les revenus et les dépenses mensuelles avec un design épuré."""
    if df.empty:
        return px.scatter(title="Aucune donnée pour le graphique")

    # Resampling sur l'index Datetime
    rev = df[df['type'] == 'Revenu'].resample('ME')['amount'].sum().rename('Revenu')
    dep = df[df['type'] == 'Dépense'].resample('ME')['amount'].sum().rename('Dépense')

    plot_df = pd.concat([rev, dep], axis=1).fillna(0)
    # CORRECTION CRITIQUE : On extrait le mois depuis l'index, pas depuis une colonne absente
    plot_df['month'] = plot_df.index.strftime('%b %Y')

    fig = px.bar(
        plot_df, x='month', y=['Revenu', 'Dépense'],
        title='📊 Flux de Trésorerie Mensuel',
        barmode='group',
        color_discrete_map={'Revenu': '#2ecc71', 'Dépense': '#e74c3c'},
        template="plotly_white"
    )
    symbol = CURRENCY_SYMBOLS.get(base_currency, base_currency)
    fig.update_layout(xaxis_title="", yaxis_title=f"Montant ({symbol})", legend_title="")
    return fig

def plot_savings_rate(df):
    """Trace le taux d'épargne ((revenus - dépenses) / revenus, en %) à partir des données calculées."""
    if df.empty:
        return px.scatter(title="Aucune donnée pour le graphique")

    # On récupère le taux d'épargne moyen par fin de mois depuis l'index
    monthly_savings = df.resample('ME')['taux_epargne'].mean().to_frame()
    monthly_savings['month'] = monthly_savings.index.strftime('%b %Y')

    fig = px.line(
        monthly_savings, x='month', y='taux_epargne',
        title="📈 Évolution du Taux d'Épargne (%)",
        markers=True,
        template="plotly_white"
    )
    fig.update_traces(line_color='#3498db', line_width=3)
    fig.update_layout(yaxis_range=[-100, 100], xaxis_title="", yaxis_title="Taux d'épargne %")
    return fig