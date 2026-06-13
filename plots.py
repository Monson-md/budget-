import plotly.express as px
import pandas as pd

def plot_revenue_expense(df):
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
    fig.update_layout(xaxis_title="", yaxis_title="Montant (€)", legend_title="")
    return fig

def plot_profit_margin(df):
    """Trace la marge bénéficiaire (%) à partir des données calculées."""
    if df.empty:
        return px.scatter(title="Aucune donnée pour le graphique")

    # On récupère la marge moyenne par fin de mois depuis l'index
    monthly_margin = df.resample('ME')['marge'].mean().to_frame()
    monthly_margin['month'] = monthly_margin.index.strftime('%b %Y')

    fig = px.line(
        monthly_margin, x='month', y='marge',
        title='📈 Évolution de la Marge (%)',
        markers=True,
        template="plotly_white"
    )
    fig.update_traces(line_color='#3498db', line_width=3)
    fig.update_layout(yaxis_range=[-100, 100], xaxis_title="", yaxis_title="Marge %")
    return fig