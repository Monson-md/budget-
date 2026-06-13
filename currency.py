import streamlit as st
import requests

def get_exchange_rate(from_currency, to_currency="EUR"):
    """
    Récupère le taux de change en direct depuis une API gratuite.
    Si l'API est indisponible ou corrompue, utilise des taux de secours.
    """
    if from_currency == to_currency:
        return 1.0
        
    # On définit les taux de secours dès le départ pour couvrir tous les cas de panne
    fallback_rates = {
        "XOF": 0.0015,  # 1 FCFA ≈ 0.0015 Euro
        "USD": 0.92,    # 1 Dollar ≈ 0.92 Euro
        "GBP": 1.17     # 1 Livre ≈ 1.17 Euro
    }
        
    try:
        url = f"https://open.er-api.com/v6/latest/{from_currency}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if response.status_code == 200 and "rates" in data:
            if to_currency in data["rates"]:
                return data["rates"][to_currency]
    except Exception:
        # En cas de timeout ou coupure internet, on passe silencieusement au plan B
        pass
        
    # Si on arrive ici, c'est que l'API a échoué ou est incomplète -> Plan B automatique
    return fallback_rates.get(from_currency, 1.0)

def convert_amount(amount, from_currency, to_currency="EUR"):
    """Convertit un montant d'une devise vers une autre."""
    rate = get_exchange_rate(from_currency, to_currency)
    return round(amount * rate, 2)