import streamlit as st
import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# 1. CONFIGURATION & FUSEAU HORAIRE FRANÇAIS
# ==============================================================================
st.set_page_config(
    page_title="Pointeuse DFM Web",
    page_icon="⏱️",
    layout="wide"
)

# Configuration du fuseau horaire (gestion automatique UTC+1 en hiver / UTC+2 en été)
TZ_PARIS = ZoneInfo("Europe/Paris")

CONTRAT_H_JOUR = 7.0
CONTRAT_H_SEMAINE = 35.0

WS_POINTAGES = "Pointages"
WS_COMPTEURS = "Compteurs"

# ==============================================================================
# 2. CONNEXION GOOGLE SHEETS
# ==============================================================================
conn = st.connection("gsheets", type=GSheetsConnection)

# ==============================================================================
# 3. FONCTIONS UTILITAIRES & ROBUSTESSE
# ==============================================================================
def safe_float(val, default=0.0):
    """Convertit une valeur en nombre flottant de manière sécurisée (gère '1,5' et ignore les textes)."""
    try:
        if isinstance(val, str):
            val = val.replace(',', '.').strip()
        return float(val)
    except (ValueError, TypeError):
        return default

def parse_time_to_hours(t_str):
    """Convertit une heure au format HH:MM en heures décimales (ex: '08:30' -> 8.5)."""
    try:
        if not t_str or not isinstance(t_str, str) or ':' not in t_str:
            return 0.0
        h, m = map(int, t_str.split(':'))
        return h + m / 60.0
    except Exception:
        return 0.0

def load_data(worksheet_name):
    """Charge les données d'un onglet Google Sheets."""
    try:
        df = conn.read(worksheet=worksheet_name, ttl="0")
        if df is None or df.empty:
            return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"Erreur lors du chargement de l'onglet {worksheet_name} : {e}")
        return pd.DataFrame()

# ==============================================================================
# 4. BARRE LATÉRALE & NAVIGATION
# ==============================================================================
st.sidebar.title("⏱️ Pointeuse DFM")
menu = st.sidebar.radio(
    "Menu principal :",
    [
        "⚡ Saisie & Pointage Rapide",
        "📊 Historique & Compteurs",
        "🏖️ Gestion des Absences"
    ]
)

# Date et heure actuelles en France
now_paris = datetime.datetime.now(TZ_PARIS)
today_paris = now_paris.date()
now_str = now_paris.strftime("%H:%M")
today_str = today_paris.strftime("%Y-%m-%d")

st.sidebar.markdown("---")
st.sidebar.info(f"🕒 **Heure France :** {now_str}\n\n📅 **Date :** {today_str}")

# ==============================================================================
# MENU 1 : SAISIE & POINTAGE RAPIDE
# ==============================================================================
if menu == "⚡ Saisie & Pointage Rapide":
    st.title("⚡ Saisie & Pointage Rapide")
    st.write("Enregistrez vos heures de présence quotidiennes ou pointez en direct.")

    df_pointages = load_data(WS_POINTAGES)

    st.subheader("1-Clic : Pointage Rapide en Direct")
    col1, col2 = st.columns(2)

    # Pointage d'arrivée
    with col1:
        if st.button("🟢 Pointer l'ARRIVÉE maintenant", use_container_width=True):
            new_row = pd.DataFrame([{
                "Date": today_str,
                "Arrivée": now_str,
                "Pause (h)": 1.0,
                "Départ": "",
                "Heures Travaillées": 0.0,
                "H_SUP": 0.0,
                "Commentaire": "Pointage rapide Arrivée"
            }])
            if not df_pointages.empty:
                df_updated = pd.concat([df_pointages, new_row], ignore_index=True)
            else:
                df_updated = new_row
            conn.update(worksheet=WS_POINTAGES, data=df_updated)
            st.success(f"✅ Arrivée enregistrée à {now_str} !")
            st.rerun()

    # Pointage de départ
    with col2:
        if st.button("🔴 Pointer le DÉPART maintenant", use_container_width=True):
            if not df_pointages.empty and today_str in df_pointages["Date"].astype(str).values:
                idx = df_pointages[df_pointages["Date"].astype(str) == today_str].index[-1]
                arr_str = str(df_pointages.loc[idx, "Arrivée"])
                pause = safe_float(df_pointages.loc[idx, "Pause (h)"], default=1.0)
                
                arr_h = parse_time_to_hours(arr_str)
                dep_h = parse_time_to_hours(now_str)
                
                worked = max(0.0, (dep_h - arr_h) - pause)
                overtime = max(0.0, worked - CONTRAT_H_JOUR)
                
                df_pointages.loc[idx, "Départ"] = now_str
                df_pointages.loc[idx, "Heures Travaillées"] = round(worked, 2)
                df_pointages.loc[idx, "H_SUP"] = round(overtime, 2)
                
                conn.update(worksheet=WS_POINTAGES, data=df_pointages)
                st.success(f"✅ Départ enregistré à {now_str} ! ({worked:.2f}h travaillées, +{overtime:.2f}h SUP)")
                st.rerun()
            else:
                st.warning("⚠️ Aucun pointage d'arrivée trouvé pour aujourd'hui. Effectuez une saisie manuelle ci-dessous.")

    st.markdown("---")
    st.subheader("📝 Saisie Manuelle Complète")

    with st.form("form_saisie_manuelle"):
        f_date = st.date_input("Date", value=today_paris)
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            f_arrivee = st.text_input("Heure Arrivée (HH:MM)", value="08:00")
        with col_b:
            f_pause = st.text_input("Pause déjeuner (heures)", value="1,0")
        with col_c:
            f_depart = st.text_input("Heure Départ (HH:MM)", value=now_str)
        
        f_comment = st.text_input("Commentaire / Projet", value="")
        submitted = st.form_submit_button("💾 Enregistrer la journée")

        if submitted:
            pause_val = safe_float(f_pause, default=1.0)
            arr_h = parse_time_to_hours(f_arrivee)
            dep_h = parse_time_to_hours(f_depart)
            
            worked = max(0.0, (dep_h - arr_h) - pause_val)
            overtime = max(0.0, worked - CONTRAT_H_JOUR)
            
            date_s = f_date.strftime("%Y-%m-%d")
            
            new_data = {
                "Date": date_s,
                "Arrivée": f_arrivee,
                "Pause (h)": pause_val,
                "Départ": f_depart,
                "Heures Travaillées": round(worked, 2),
                "H_SUP": round(overtime, 2),
                "Commentaire": f_comment
            }
            
            if not df_pointages.empty and date_s in df_pointages["Date"].astype(str).values:
                df_pointages.loc[df_pointages["Date"].astype(str) == date_s, list(new_data.keys())] = list(new_data.values())
                df_updated = df_pointages
            else:
                df_updated = pd.concat([df_pointages, pd.DataFrame([new_data])], ignore_index=True)
                
            conn.update(worksheet=WS_POINTAGES, data=df_updated)
            st.success(f"Journée du {date_s} enregistrée : {worked:.2f}h travaillées (+{overtime:.2f}h SUP)")
            st.rerun()

# ==============================================================================
# MENU 2 : HISTORIQUE & COMPTEURS
# ==============================================================================
elif menu == "📊 Historique & Compteurs":
    st.title("📊 Historique des Pointages & Compteurs")
    
    df_pointages = load_data(WS_POINTAGES)
    df_compteurs = load_data(WS_COMPTEURS)

    # Calcul des totaux de présence
    tot_worked = 0.0
    tot_hsup = 0.0
    if not df_pointages.empty and "Heures Travaillées" in df_pointages.columns:
        tot_worked = df_pointages["Heures Travaillées"].apply(safe_float).sum()
        tot_hsup = df_pointages["H_SUP"].apply(safe_float).sum()

    # Extraction du solde CP sans faire de crash sur la ligne "1er juin - 31 mai"
    solde_cp = 0.0
    if not df_compteurs.empty:
        for idx, row in df_compteurs.iterrows():
            param = str(row.get("Paramètre", "")).strip().lower()
            if "solde cp" in param or "cp" in param:
                solde_cp = safe_float(row.get("Valeur", 0.0))

    # Affichage des métriques
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Total Travaillé", f"{tot_worked:.2f} h")
    with col_m2:
        st.metric("Heures Supp. Cumulées", f"{tot_hsup:.2f} h")
    with col_m3:
        st.metric("Solde CP", f"{solde_cp:.1f} j")
    with col_m4:
        st.metric("Contrat Hebdo", f"{CONTRAT_H_SEMAINE} h")

    st.markdown("---")
    st.subheader("📋 Historique complet")
    if not df_pointages.empty:
        st.dataframe(df_pointages, use_container_width=True)
    else:
        st.info("Aucun pointage enregistré dans Google Sheets.")

# ==============================================================================
# MENU 3 : GESTION DES ABSENCES
# ==============================================================================
elif menu == "🏖️ Gestion des Absences":
    st.title("🏖️ Enregistrement des Absences / Congés")

    df_compteurs = load_data(WS_COMPTEURS)
    df_pointages = load_data(WS_POINTAGES)

    with st.form("form_absence"):
        type_absence = st.selectbox("Type d'absence", ["Congé Payé (CP)", "RTT", "Maladie", "Sans Solde", "Autre"])
        date_debut = st.date_input("Date de début", value=today_paris)
        date_fin = st.date_input("Date de fin", value=today_paris)
        nb_jours = st.number_input("Nombre de jours ouvrés", min_value=0.5, max_value=30.0, step=0.5, value=1.0)
        motif = st.text_input("Motif / Remarque", value="")
        
        btn_submit = st.form_submit_button("💾 Valider l'absence")

        if btn_submit:
            desc_absence = f"ABSENCE: {type_absence} ({motif})"
            
            new_absence = {
                "Date": date_debut.strftime("%Y-%m-%d"),
                "Arrivée": "ABSENT",
                "Pause (h)": 0.0,
                "Départ": "ABSENT",
                "Heures Travaillées": 0.0,
                "H_SUP": 0.0,
                "Commentaire": desc_absence
            }
            
            df_pointages = pd.concat([df_pointages, pd.DataFrame([new_absence])], ignore_index=True)
            conn.update(worksheet=WS_POINTAGES, data=df_pointages)

            # Mise à jour du solde CP (filtre exclusivement les lignes numériques)
            if type_absence == "Congé Payé (CP)" and not df_compteurs.empty:
                for idx, row in df_compteurs.iterrows():
                    param = str(row.get("Paramètre", "")).strip().lower()
                    if "solde cp" in param or "cp" in param:
                        val_actuelle = safe_float(row.get("Valeur", 0.0))
                        df_compteurs.loc[idx, "Valeur"] = max(0.0, val_actuelle - nb_jours)
                        df_compteurs.loc[idx, "Dernière MAJ"] = now_paris.strftime("%Y-%m-%d %H:%M")
                
                conn.update(worksheet=WS_COMPTEURS, data=df_compteurs)

            st.success(f"Absence ({type_absence}) enregistrée avec succès !")
            st.rerun()
