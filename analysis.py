import pandas as pd
from prophet import Prophet
import streamlit as st

def prepare_data(entries):
    """Prépare les données pour l'analyse et le plotting."""
    if not entries:
        return pd.DataFrame()
    
    # Conversion en DataFrame
    df = pd.DataFrame(entries)
    
    # Conversion des types
    df['date'] = pd.to_datetime(df['date'])
    df['revenu'] = pd.to_numeric(df['revenu'], errors='coerce').fillna(0)
    df['depense'] = pd.to_numeric(df['depense'], errors='coerce').fillna(0)
    
    # Calcul des métriques
    df['profit'] = df['revenu'] - df['depense']
    # Évite la division par zéro
    df['marge'] = ((df['profit']/df['revenu']).replace([float('inf'), -float('inf')], 0) * 100).round(2)
    
    # Indexation par date pour les graphiques
    df.set_index('date', inplace=True)
    df.sort_index(inplace=True)
    
    return df

def forecast_prophet(df):
    """Prédit le profit pour le mois prochain en utilisant Prophet."""
    
    # La prévision nécessite au moins deux points de données distincts
    if len(df.index.unique()) < 2:
        return None
    
    try:
        # Prophet nécessite des colonnes 'ds' (datestamp) et 'y' (valeur)
        df_p = df.reset_index()[['date','profit']].rename(columns={'date':'ds','profit':'y'})
        
        # Prophet est sensible aux données groupées, on agrège par jour ou par mois si les dates sont trop rapprochées
        df_p = df_p.groupby('ds')['y'].sum().reset_index()

        model = Prophet(interval_width=0.95, daily_seasonality=False)
        model.fit(df_p)
        
        # Prédit pour les 30 prochains jours (prochain mois)
        future = model.make_future_dataframe(periods=30, freq='D')
        forecast = model.predict(future)
        
        # On ne prend que la valeur moyenne prédite pour le dernier jour de la prévision
        return forecast.iloc[-1]['yhat']

    except Exception as e:
        st.error(f"Erreur lors de la prévision Prophet : {e}")
        return None