import calendar
from datetime import date
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
    
    # Agrégation mensuelle pour le calcul exact du taux d'épargne
    monthly = df.resample('ME').agg({'profit': 'sum'})
    monthly['rev_total'] = df[df['type'] == 'Revenu'].resample('ME')['amount'].sum().fillna(0)

    # Taux d'épargne mensuel réel : (revenus - dépenses) / revenus * 100.
    # monthly['profit'] vaut déjà (revenus - dépenses) du mois (profit par
    # ligne = montant si Revenu, -montant si Dépense), donc la formule est
    # directement profit / rev_total * 100.
    monthly['taux_epargne'] = (monthly['profit'] / monthly['rev_total']) * 100
    monthly['taux_epargne'] = monthly['taux_epargne'].replace([float('inf'), -float('inf')], 0).fillna(0)

    # Cartographie propre sur l'index
    df['taux_epargne'] = df.index.to_period('M').map(monthly['taux_epargne'].to_dict())

    return df

def compute_monthly_budget_status(df, today=None):
    """Calcule le solde disponible du mois en cours et le budget journalier
    restant, pour la carte "Combien puis-je dépenser ?".

    Retourne None s'il n'y a aucune transaction ce mois-ci (df vide ou aucune
    ligne dans le mois courant) : la carte ne doit alors pas s'afficher.
    """
    if df.empty:
        return None

    if today is None:
        today = date.today()

    df_month = df[(df.index.year == today.year) & (df.index.month == today.month)]
    if df_month.empty:
        return None

    # profit par ligne = montant si Revenu, -montant si Dépense (déjà calculé
    # dans prepare_data) : la somme du mois est donc directement le solde
    # disponible (revenus du mois - dépenses du mois déjà enregistrées).
    balance = df_month['profit'].sum()

    last_day = calendar.monthrange(today.year, today.month)[1]
    month_end = date(today.year, today.month, last_day)
    days_remaining = (month_end - today).days + 1

    return {
        "balance": balance,
        "days_remaining": days_remaining,
        "daily_budget": balance / days_remaining,
        "month_end": month_end,
    }

# En dessous de ce nombre de mois d'historique, une prévision Prophet n'est
# pas assez fiable pour être présentée comme telle sous "Prévision IA".
FORECAST_MIN_MONTHS = 3


def _forecast_label(months_used):
    """Libellé reflétant la fiabilité de la prévision selon l'historique disponible."""
    if months_used < 6:
        return "Estimation expérimentale"
    if months_used < 12:
        return "Prévision"
    return "Prévision (historique suffisant)"


@st.cache_data(ttl=3600, show_spinner=False)
def forecast_prophet(df):
    """Prédit le profit du mois prochain, avec une fourchette (yhat_lower/yhat_upper)
    plutôt qu'un chiffre unique.

    Retourne toujours un dict avec au moins "available" et "months_used" :
    - available=False, months_used<FORECAST_MIN_MONTHS : pas assez d'historique.
    - available=False, months_used>=FORECAST_MIN_MONTHS : Prophet indisponible
      ou échec du calcul (binaire cmdstan manquant, etc.).
    - available=True : yhat/yhat_lower/yhat_upper/label présents.
    """
    if not PROPHET_AVAILABLE or df.empty:
        return {"available": False, "months_used": 0}

    ts = df['profit'].resample('ME').sum().reset_index()
    ts.columns = ['ds', 'y']
    months_used = len(ts)

    if months_used < FORECAST_MIN_MONTHS:
        return {"available": False, "months_used": months_used}

    try:
        ts['ds'] = ts['ds'].dt.tz_localize(None)
        m = Prophet(interval_width=0.95, daily_seasonality=False, weekly_seasonality=False, yearly_seasonality=False)
        m.fit(ts)

        future = m.make_future_dataframe(periods=1, freq='ME')
        forecast = m.predict(future)
        last = forecast.iloc[-1]

        return {
            "available": True,
            "months_used": months_used,
            "label": _forecast_label(months_used),
            "yhat": last['yhat'],
            "yhat_lower": last['yhat_lower'],
            "yhat_upper": last['yhat_upper'],
        }
    except Exception:
        return {"available": False, "months_used": months_used}