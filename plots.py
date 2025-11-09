import plotly.graph_objects as go
import pandas as pd

def plot_revenue_expense(df):
    """Graphique en barres pour la comparaison Revenus vs Dépenses par date."""
    
    # Agrégation journalière pour une meilleure lisibilité si beaucoup d'entrées
    df_daily = df.groupby(df.index).agg({
        'revenu': 'sum',
        'depense': 'sum'
    })
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(x=df_daily.index, y=df_daily['revenu'], name='Revenu', marker_color='green'))
    fig.add_trace(go.Bar(x=df_daily.index, y=df_daily['depense'], name='Dépense', marker_color='red'))
    
    fig.update_layout(
        barmode='group', 
        title="📈 Revenus vs Dépenses (Somme Journalière)",
        xaxis_title="Date",
        yaxis_title="Montant en EUR (€)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def plot_profit_margin(df):
    """Graphique combiné pour le Profit (barre) et la Marge (%) (ligne)."""
    
    # Agrégation journalière
    df_daily = df.groupby(df.index).agg({
        'profit': 'sum',
        'marge': 'mean' # Utilise la moyenne de la marge pour le jour
    })
    
    fig = go.Figure()
    
    # Trace 1: Profit (Barres, axe Y primaire)
    fig.add_trace(go.Bar(
        x=df_daily.index, 
        y=df_daily['profit'], 
        name='Profit (€)',
        marker_color='blue',
        opacity=0.6,
        yaxis='y1'
    ))
    
    # Trace 2: Marge (Ligne, axe Y secondaire)
    fig.add_trace(go.Scatter(
        x=df_daily.index, 
        y=df_daily['marge'], 
        mode='lines+markers', 
        name='Marge (%)', 
        line_color='orange',
        yaxis='y2'
    ))
    
    fig.update_layout(
    # ... autres arguments de layout ...
    yaxis=dict(
        title=dict( # Utilisez 'title' comme un dictionnaire
            text='Votre Titre d\'Axe Y', # Optionnel : définir le texte ici ou dans l'argument de niveau supérieur
            font=dict(
                size=16,
                color='black',
                family='Arial'
            ) # Définissez la police DANS 'title'
        ),
        # Si vous voulez styliser les étiquettes des graduations (les nombres/dates)
        tickfont=dict(
            size=12, 
            color='grey'
        )
    )
)
    return fig