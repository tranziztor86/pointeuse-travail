import streamlit as st
import datetime
from datetime import timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION PAGE WEB ---
st.set_page_config(page_title="DFM Europe - Pointeuse & Congés", page_icon="🕒", layout="wide")

CONTRAT_H_JOUR = 7.0
WS_POINTAGES = "Pointages"
WS_ABSENCES = "Absences"

def calculate_worked_hours(arrival_str, departure_str, break_hours):
    """Calcule la durée travaillée et les heures supplémentaires."""
    if not arrival_str or not departure_str:
        return 0.0, 0.0
    try:
        h1, m1 = map(int, str(arrival_str).split(':'))
        h2, m2 = map(int, str(departure_str).split(':'))
        t1 = h1 * 60 + m1
        t2 = h2 * 60 + m2
        if t2 < t1:
            t2 += 24 * 60
        worked_min = max(0, (t2 - t1) - int(float(break_hours) * 60))
        worked_hours = round(worked_min / 60, 2)
        overtime = max(0.0, round(worked_hours - CONTRAT_H_JOUR, 2))
        return worked_hours, overtime
    except Exception:
        return 0.0, 0.0

st.title("🕒 DFM Europe - Pointeuse & Suivi des Congés")
st.caption("Chef de projet IoT - Saisie Rapide, Congés & Synchronisation Google Sheets")

# --- CONNEXION GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"❌ Erreur de connexion à Google Sheets : {e}")
    st.stop()

# --- MENU NAVIGATION ---
menu = st.sidebar.radio(
    "Navigation", 
    ["⚡ Saisie Semaine", "🌴 Congés & Récupérations", "📊 Historique & Soldes"]
)

# ==============================================================================
# MENU 1 : SAISIE SEMAINE
# ==============================================================================
if menu == "⚡ Saisie Semaine":
    st.subheader("⚡ Saisie rapide du Lundi au Vendredi")
    
    today = datetime.date.today()
    monday = today - timedelta(days=today.weekday())
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
    
    with st.form("form_semaine"):
        st.write("Ajustez vos horaires de présence puis enregistrez :")
        
        cols_hdr = st.columns([1.5, 2, 2, 2, 1.5, 3])
        cols_hdr[0].write("**Jour**")
        cols_hdr[1].write("**Date**")
        cols_hdr[2].write("**Arrivée**")
        cols_hdr[3].write("**Départ**")
        cols_hdr[4].write("**Pause (h)**")
        cols_hdr[5].write("**Commentaire**")
        
        entries = []
        for i, day_name in enumerate(days):
            d_date = monday + timedelta(days=i)
            c = st.columns([1.5, 2, 2, 2, 1.5, 3])
            
            c[0].write(f"**{day_name}**")
            dt = c[1].date_input(f"date_{i}", value=d_date, label_visibility="collapsed")
            arr = c[2].time_input(f"arr_{i}", value=datetime.time(8, 30), label_visibility="collapsed")
            dep = c[3].time_input(f"dep_{i}", value=datetime.time(16, 30), label_visibility="collapsed")
            pause = c[4].number_input(f"pause_{i}", value=1.0, step=0.5, label_visibility="collapsed")
            com = c[5].text_input(f"com_{i}", key=f"com_{i}", label_visibility="collapsed")
            
            arr_str = arr.strftime("%H:%M")
            dep_str = dep.strftime("%H:%M")
            worked, overtime = calculate_worked_hours(arr_str, dep_str, pause)
            
            entries.append({
                "Date": dt.strftime("%Y-%m-%d"),
                "Heure Arrivée": arr_str,
                "Heure Départ": dep_str,
                "Pause (H)": pause,
                "Durée Travaillée": worked,
                "H. Supp": overtime,
                "Commentaire": com
            })
            
        submitted = st.form_submit_button("💾 Enregistrer la semaine")
        
        if submitted:
            try:
                try:
                    existing_df = conn.read(worksheet=WS_POINTAGES, ttl="0")
                except Exception:
                    existing_df = pd.DataFrame()

                new_df = pd.DataFrame(entries)
                
                if existing_df is None or existing_df.empty:
                    updated_df = new_df
                else:
                    dates_to_add = set(new_df["Date"].astype(str))
                    if "Date" in existing_df.columns:
                        existing_df = existing_df[~existing_df["Date"].astype(str).isin(dates_to_add)]
                    updated_df = pd.concat([existing_df, new_df], ignore_index=True)
                
                conn.update(worksheet=WS_POINTAGES, data=updated_df)
                st.success("✅ Semaine enregistrée avec succès dans Google Sheets !")
                st.dataframe(new_df)
            except Exception as e:
                st.error(f"❌ Erreur lors de l'enregistrement : {e}")

# ==============================================================================
# MENU 2 : CONGÉS & RÉCUPÉRATIONS
# ==============================================================================
elif menu == "🌴 Congés & Récupérations":
    st.subheader("🌴 Declaration de Congés, Récupérations & Absences")
    
    with st.form("form_absence"):
        type_absence = st.selectbox(
            "Type d'événement",
            ["Congé Payé (CP)", "Récupération H.SUP", "Arrêt Maladie", "Absence Exceptionnelle", "Autre"]
        )
        
        col_d1, col_d2 = st.columns(2)
        date_debut = col_d1.date_input("Date de début", datetime.date.today())
        date_fin = col_d2.date_input("Date de fin", datetime.date.today())
        
        col_v1, col_v2 = st.columns(2)
        
        if type_absence == "Récupération H.SUP":
            heures_recup = col_v1.number_input("Nombre d'heures récupérées (H)", min_value=0.5, value=7.0, step=0.5)
            jours_deduits = 0.0
        elif type_absence == "Congé Payé (CP)":
            jours_deduits = col_v1.number_input("Nombre de jours posés", min_value=0.5, value=1.0, step=0.5)
            heures_recup = 0.0
        else:
            jours_deduits = 0.0
            heures_recup = 0.0
            
        motif = st.text_input("Commentaire / Motif")
        
        submit_absence = st.form_submit_button("💾 Enregistrer l'absence")
        
        if submit_absence:
            try:
                try:
                    abs_df = conn.read(worksheet=WS_ABSENCES, ttl="0")
                except Exception:
                    abs_df = pd.DataFrame()

                new_abs = pd.DataFrame([{
                    "Date Demande": datetime.date.today().strftime("%Y-%m-%d"),
                    "Type": type_absence,
                    "Date Début": date_debut.strftime("%Y-%m-%d"),
                    "Date Fin": date_fin.strftime("%Y-%m-%d"),
                    "Jours CP": jours_deduits,
                    "Heures Récup H.SUP": heures_recup,
                    "Motif": motif
                }])
                
                if abs_df is None or abs_df.empty:
                    updated_abs = new_abs
                else:
                    updated_abs = pd.concat([abs_df, new_abs], ignore_index=True)
                
                conn.update(worksheet=WS_ABSENCES, data=updated_abs)
                st.success(f"✅ Événement '{type_absence}' enregistré avec succès !")
                st.dataframe(new_abs)
            except Exception as e:
                st.error(f"❌ Erreur lors de l'enregistrement de l'absence : {e}")

# ==============================================================================
# MENU 3 : HISTORIQUE & COMPTEURS
# ==============================================================================
elif menu == "📊 Historique & Soldes":
    st.subheader("📊 Compteurs Globaux & Historique")
    
    # Lecture des pointages
    try:
        df_p = conn.read(worksheet=WS_POINTAGES, ttl="0")
    except Exception:
        df_p = pd.DataFrame()

    # Lecture des absences
    try:
        df_a = conn.read(worksheet=WS_ABSENCES, ttl="0")
    except Exception:
        df_a = pd.DataFrame()

    # Calculs
    tot_worked = pd.to_numeric(df_p.get("Durée Travaillée", 0), errors='coerce').sum() if df_p is not None and not df_p.empty else 0.0
    tot_overtime_gained = pd.to_numeric(df_p.get("H. Supp", 0), errors='coerce').sum() if df_p is not None and not df_p.empty else 0.0
    
    tot_overtime_used = pd.to_numeric(df_a.get("Heures Récup H.SUP", 0), errors='coerce').sum() if df_a is not None and not df_a.empty else 0.0
    tot_cp_used = pd.to_numeric(df_a.get("Jours CP", 0), errors='coerce').sum() if df_a is not None and not df_a.empty else 0.0
    
    solde_h_sup = tot_overtime_gained - tot_overtime_used

    # Affichage des métriques
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Heures Travaillées", f"{tot_worked:.2f} h")
    m2.metric("Heures Supp. Acquises", f"+{tot_overtime_gained:.2f} h")
    m3.metric("Solde Net H.SUP", f"{solde_h_sup:.2f} h", delta=f"-{tot_overtime_used:.2f} h récupérées")
    m4.metric("Jours CP Posés", f"{tot_cp_used:.1f} j")

    st.markdown("---")
    
    tab1, tab2 = st.tabs(["📝 Registre des Pointages", "🌴 Registre des Absences"])
    
    with tab1:
        if df_p is not None and not df_p.empty:
            st.dataframe(df_p)
        else:
            st.info("Aucun pointage trouvé.")
            
    with tab2:
        if df_a is not None and not df_a.empty:
            st.dataframe(df_a)
        else:
            st.info("Aucune absence ou récupération enregistrée.")
