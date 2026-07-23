import streamlit as st
import datetime
from datetime import timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION PAGE WEB ---
st.set_page_config(page_title="DFM Europe - Pointeuse Web", page_icon="🕒", layout="wide")

CONTRAT_H_JOUR = 7.0
WORKSHEET_NAME = "Pointages"  # ⚠️ Doit être le nom exact de votre onglet dans Google Sheet

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

st.title("🕒 DFM Europe - Pointeuse Web")
st.caption("Chef de projet IoT - Saisie Rapide & Synchronisation Google Sheets")

# --- CONNEXION GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"❌ Erreur de connexion à Google Sheets. Vérifiez vos Secrets Streamlit.\nDétail : {e}")
    st.stop()

# Barre latérale
menu = st.sidebar.radio("Navigation", ["⚡ Saisie Semaine", "📊 Historique & Compteurs"])

if menu == "⚡ Saisie Semaine":
    st.subheader("⚡ Saisie rapide du Lundi au Vendredi")
    
    today = datetime.date.today()
    monday = today - timedelta(days=today.weekday())
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
    
    with st.form("form_semaine"):
        st.write("Ajustez vos horaires si nécessaire puis validez :")
        
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
            
        submitted = st.form_submit_button("💾 Enregistrer la semaine dans Google Sheets")
        
        if submitted:
            try:
                # Lecture des données existantes
                try:
                    existing_df = conn.read(worksheet=WORKSHEET_NAME, ttl="0")
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
                
                # Mise à jour sur Google Sheets
                conn.update(worksheet=WORKSHEET_NAME, data=updated_df)
                st.success("✅ Semaine enregistrée avec succès dans Google Sheets !")
                st.dataframe(new_df)
            except Exception as e:
                st.error(f"❌ Erreur lors de l'enregistrement dans Google Sheets :\n{e}")

elif menu == "📊 Historique & Compteurs":
    st.subheader("📊 Registre complet des Pointages")
    try:
        df = conn.read(worksheet=WORKSHEET_NAME, ttl="0")
        if df is not None and not df.empty:
            st.dataframe(df)
            
            col1, col2 = st.columns(2)
            total_worked = pd.to_numeric(df.get("Durée Travaillée", 0), errors='coerce').sum()
            total_overtime = pd.to_numeric(df.get("H. Supp", 0), errors='coerce').sum()
            
            col1.metric("Total Heures Travaillées", f"{total_worked:.2f} h")
            col2.metric("Total Heures Supplémentaires", f"{total_overtime:.2f} h")
        else:
            st.info("Aucun pointage trouvé dans l'onglet 'Pointages'.")
    except Exception as e:
        st.error(f"Impossible de lire le Google Sheet : {e}")
