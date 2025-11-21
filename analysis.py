import pandas as pd
import streamlit as st # <<< AJOUT CRITIQUE

# Nécessite prophet dans requirements.txt
try:
    from prophet import Prophet 
except ImportError:
    # L'utilisation de st.warning nécessite que Streamlit soit importé
    st.warning("La librairie Prophet n'est pas installée. Les prévisions ne fonctionneront pas.")


def prepare_data(entries):
    """
    Transforme la liste d'entrées Firebase en DataFrame pour l'analyse.
    Ajoute les colonnes de profit et de marge.
    """
    if not entries:
        return pd.DataFrame()

    df = pd.DataFrame(entries)
    
    # Conversion de types
    df['date'] = pd.to_datetime(df['date'])
    df['amount'] = pd.to_numeric(df['amount'])
    
    # Calcul du profit/perte pour chaque entrée
    df['profit'] = df.apply(lambda row: row['amount'] if row['type'] == 'Revenu' else -row['amount'], axis=1)
    
    # Regroupement par mois (pour les graphiques)
    df = df.set_index('date').sort_index()
    
    # Calcul des totaux mensuels pour la marge
    monthly_data = df.resample('M').agg(
        Revenu=('amount', lambda x: x[df.loc[x.index, 'type'] == 'Revenu'].sum()),
        Dépense=('amount', lambda x: x[df.loc[x.index, 'type'] == 'Dépense'].sum()),
        profit=('profit', 'sum')
    ).fillna(0)
    
    # Calcul de la marge (pourcentage)
    monthly_data['marge'] = ((monthly_data['Revenu'] - monthly_data['Dépense']) / monthly_data['Revenu']) * 100
    monthly_data.loc[monthly_data['Revenu'] == 0, 'marge'] = 0
    
    # Fusionner la marge mensuelle avec le DF original pour l'affichage (simplification)
    # Pour un dashboard réel, on utiliserait le monthly_data pour les plots
    df['marge'] = df.index.to_period('M').map(monthly_data['marge'].to_dict())
    
    return df

def forecast_prophet(df):
    """
    Prédit le profit total du mois prochain en utilisant Prophet.
    Nécessite au moins 3 points de données mensuelles.
    """
    if 'Prophet' not in globals():
        return None

    # Agrégation mensuelle des profits
    ts = df['profit'].resample('M').sum().reset_index()
    ts.columns = ['ds', 'y']
    
    if len(ts) < 3:
        return None # Pas assez de données pour la prévision

    # Modèle Prophet
    m = Prophet(daily_seasonality=False, weekly_seasonality=False)
    m.fit(ts)
    
    # Prédiction pour le mois suivant
    future = m.make_future_dataframe(periods=1, freq='M')
    forecast = m.predict(future)
    
    # Retourne la prévision pour le dernier point (le mois prochain)
    return forecast['yhat'].iloc[-1]