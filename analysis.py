import pandas as pd
import streamlit as st

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except Exception:
    # On capture toute exception (pas seulement ImportError) car l'import de
    # Prophet peut aussi échouer au runtime (ex: binaire cmdstan manquant).
    Prophet = None
    PROPHET_AVAILABLE = False

def prepare_data(entries):
    """Transforme les données brutes Firestore en DataFrame structuré."""
    if not entries:
        return pd.DataFrame()

    df = pd.DataFrame(entries)

    # Des documents Firestore incomplets (saisis avant un changement de schéma,
    # ou corrompus) ne doivent pas planter tout le dashboard avec un KeyError.
    if 'date' not in df.columns:
        df['date'] = pd.Timestamp.now()
    if 'type' not in df.columns:
        df['type'] = 'Dépense'
    if 'amount' not in df.columns:
        df['amount'] = 0

    df['date'] = pd.to_datetime(df['date'])
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    
    # Calcul du profit net par ligne
    df['profit'] = df.apply(lambda row: row['amount'] if row['type'] == 'Revenu' else -row['amount'], axis=1)
    
    df = df.set_index('date').sort_index()
    
    # Agrégation mensuelle pour le calcul exact des marges
    monthly = df.resample('ME').agg({'profit': 'sum'}) 
    monthly['rev_total'] = df[df['type'] == 'Revenu'].resample('ME')['amount'].sum().fillna(0)
    
    # Calcul de la marge mensuelle réelle
    monthly['marge'] = (monthly['profit'] / monthly['rev_total']) * 100
    monthly['marge'] = monthly['marge'].replace([float('inf'), -float('inf')], 0).fillna(0)
    
    # Cartographie propre sur l'index
    df['marge'] = df.index.to_period('M').map(monthly['marge'].to_dict())
    
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def forecast_prophet(df):
    """Prédit le profit du mois prochain. Retourne None si indisponible."""
    if not PROPHET_AVAILABLE or df.empty:
        return None

    ts = df['profit'].resample('ME').sum().reset_index()
    ts.columns = ['ds', 'y']
    
    if len(ts) < 2: 
        return None

    try:
        ts['ds'] = ts['ds'].dt.tz_localize(None)
        m = Prophet(interval_width=0.95, daily_seasonality=False, weekly_seasonality=False, yearly_seasonality=False)
        m.fit(ts)
        
        future = m.make_future_dataframe(periods=1, freq='ME')
        forecast = m.predict(future)
        
        return forecast['yhat'].iloc[-1]
    except Exception:
        return None