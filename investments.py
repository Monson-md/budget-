import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px  # Ajout pour un graphique pro du portefeuille

def calculate_roi(initial_value, current_value):
    """Calcule le Retour sur Investissement (ROI)."""
    if initial_value <= 0: return 0
    return ((current_value - initial_value) / initial_value) * 100

def compound_interest_simulation(principal, annual_rate, years, monthly_contribution):
    """Simule la croissance d'un capital avec intérêts composés."""
    rate = annual_rate / 100
    months = years * 12
    monthly_rate = rate / 12
    
    data = []
    balance = principal
    for month in range(1, months + 1):
        balance = (balance + monthly_contribution) * (1 + monthly_rate)
        # On regroupe par année pour que le graphique soit plus lisible
        if month % 12 == 0 or month == 1:
            data.append({"Année": round(month / 12, 1), "Solde (€)": round(balance, 2)})
    
    return pd.DataFrame(data)

def investment_dashboard(db, uid):
    """Interface pour gérer les investissements."""
    st.subheader("🚀 Gestion de Portefeuille & Investissements")
    
    col1, col2 = st.columns([1, 1.2])
    
    with col1:
        st.markdown("### 📈 Ajouter un Actif")
        with st.form("inv_form", clear_on_submit=True):
            asset_name = st.text_input("Nom de l'actif (ex: Bitcoin, Action Apple)")
            asset_type = st.selectbox("Type", ["Action", "Crypto", "Or", "Immobilier", "Autre"])
            initial_cost = st.number_input("Coût d'achat total (€)", min_value=0.0, step=10.0)
            current_val = st.number_input("Valeur actuelle (€)", min_value=0.0, step=10.0)
            
            if st.form_submit_button("Ajouter au portefeuille", use_container_width=True):
                if asset_name: # Sécurité : vérifier que le nom n'est pas vide
                    new_inv = {
                        "name": asset_name,
                        "type": asset_type,
                        "initial_cost": initial_cost,
                        "current_value": current_val,
                        "roi": calculate_roi(initial_cost, current_val)
                    }
                    collection_name = f"investments_{uid}"
                    if db.add_entry(collection_name, new_inv):
                        st.success(f"🎯 {asset_name} ajouté avec succès !")
                        st.rerun()
                else:
                    st.error("Veuillez donner un nom à votre actif.")

    with col2:
        st.markdown("### 🔮 Simulateur d'Intérêts Composés")
        p = st.number_input("Capital initial (€)", value=1000, step=100)
        r = st.slider("Taux d'intérêt annuel estimé (%)", 1, 20, 8)
        y = st.slider("Nombre d'années de projection", 1, 40, 10)
        m = st.number_input("Épargne mensuelle ajoutée (€)", value=100, step=10)
        
        df_sim = compound_interest_simulation(p, r, y, m)
        final_val = df_sim["Solde (€)"].iloc[-1]
        total_invested = p + (m * y * 12)
        total_gain = final_val - total_invested
        
        # Affichage élégant des résultats du simulateur
        sc1, sc2 = st.columns(2)
        with sc1:
            st.metric("Valeur Finale", f"{final_val:,.2f} €")
        with sc2:
            st.metric("Intérêts Générés", f"{total_gain:,.2f} €", delta=f"Total investi: {total_invested:,.0f}€", delta_color="normal")
        
        # Graphique de simulation interactif
        fig_sim = px.area(df_sim, x="Année", y="Solde (€)", title="Projection de ta Richesse", color_discrete_sequence=["#3498db"])
        st.plotly_chart(fig_sim, use_container_width=True)

    # --- AFFICHAGE ET ANALYSE DU PORTEFEUILLE REEL ---
    st.markdown("---")
    st.subheader("📂 Mon Portefeuille Actuel")
    
    inv_data = db.get_entries(f"investments_{uid}")
    if inv_data:
        df_inv = pd.DataFrame(inv_data)
        
        # S'assurer que toutes les colonnes requises existent pour éviter un crash alternatif
        for col in ["name", "type", "initial_cost", "current_value", "roi"]:
            if col not in df_inv.columns:
                df_inv[col] = 0 if col != "name" and col != "type" else "Inconnu"

        # Séparation de l'écran : Tableau à gauche, Répartition graphique à droite
        view_col1, view_col2 = st.columns([1.2, 1])
        
        with view_col1:
            # Formatage propre des colonnes pour l'affichage de l'historique actif
            st.dataframe(
                df_inv[["name", "type", "initial_cost", "current_value", "roi"]], 
                column_config={
                    "name": "Actif",
                    "type": "Catégorie",
                    "initial_cost": st.column_config.NumberColumn("Coût d'Achat", format="%.2f €"),
                    "current_value": st.column_config.NumberColumn("Valeur Actuelle", format="%.2f €"),
                    "roi": st.column_config.NumberColumn("ROI (%)", format="%.2f %%"),
                },
                use_container_width=True
            )
            
        with view_col2:
            # Graphique camembert de la répartition des investissements
            fig_pie = px.pie(
                df_inv, 
                values='current_value', 
                names='type', 
                title='Répartition par Catégorie d\'Actifs',
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("💡 Aucun investissement enregistré pour le moment. Utilisez le formulaire ci-dessus pour ajouter vos premières actions ou cryptos.")