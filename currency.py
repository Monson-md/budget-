import streamlit as st
import requests

# Symbole d'affichage par devise de référence supportée (XOF en tête : c'est
# la devise par défaut pour le public cible Mali / Afrique de l'Ouest).
CURRENCY_SYMBOLS = {
    "XOF": "FCFA",
    "EUR": "€",
    "USD": "$",
    "GBP": "£",
}

# Seuil d'alerte "dépense élevée" par défaut, adapté à l'ordre de grandeur de
# chaque devise (les utilisateurs peuvent le personnaliser ensuite).
DEFAULT_ALERT_THRESHOLDS = {
    "XOF": 300000,
    "EUR": 500,
    "USD": 550,
    "GBP": 450,
}

# Taux de secours exprimés vers l'EUR (pivot intermédiaire des taux de
# secours uniquement) : utilisés pour reconstruire n'importe quelle paire
# from->to si l'API est indisponible, quelle que soit la devise de référence
# de l'utilisateur.
_FALLBACK_RATES_TO_EUR = {
    "EUR": 1.0,
    "XOF": 0.0015,  # 1 FCFA ≈ 0.0015 Euro
    "USD": 0.92,    # 1 Dollar ≈ 0.92 Euro
    "GBP": 1.17,    # 1 Livre ≈ 1.17 Euro
}

def _fallback_rate(from_currency, to_currency):
    """Taux from->to reconstruit à partir de la table de secours vers l'EUR."""
    from_to_eur = _FALLBACK_RATES_TO_EUR.get(from_currency, 1.0)
    to_to_eur = _FALLBACK_RATES_TO_EUR.get(to_currency, 1.0)
    if to_to_eur == 0:
        return 1.0
    return from_to_eur / to_to_eur

def format_amount(amount, currency="XOF"):
    """Formate un montant avec le symbole de la devise de référence donnée."""
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    return f"{amount:,.2f} {symbol}"

@st.cache_data(ttl=3600)
def get_exchange_rate_with_source(from_currency, to_currency="XOF"):
    """
    Récupère le taux de change en direct depuis une API gratuite, avec sa
    source ("api" ou "fallback") : sert à tracer, sur chaque transaction,
    si le taux vient réellement de l'API ou de la table de secours.
    Si l'API est indisponible ou corrompue, utilise des taux de secours.
    """
    if from_currency == to_currency:
        # Conversion identité (même devise) : ni appel API ni valeur de
        # secours, le taux 1.0 est exact par définition -> traité comme "api".
        return 1.0, "api"

    try:
        url = f"https://open.er-api.com/v6/latest/{from_currency}"
        response = requests.get(url, timeout=5)
        data = response.json()

        if response.status_code == 200 and "rates" in data:
            if to_currency in data["rates"]:
                return data["rates"][to_currency], "api"
    except Exception:
        # En cas de timeout ou coupure internet, on passe silencieusement au plan B
        pass

    # Si on arrive ici, c'est que l'API a échoué ou est incomplète -> Plan B automatique
    return _fallback_rate(from_currency, to_currency), "fallback"

def get_exchange_rate(from_currency, to_currency="XOF"):
    """Compatibilité : renvoie uniquement le taux, sans sa source."""
    rate, _source = get_exchange_rate_with_source(from_currency, to_currency)
    return rate

def convert_amount(amount, from_currency, to_currency="XOF"):
    """Convertit un montant d'une devise vers une autre."""
    rate = get_exchange_rate(from_currency, to_currency)
    return round(amount * rate, 2)