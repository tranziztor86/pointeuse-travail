import streamlit as st
import datetime
from datetime import timedelta
import pandas as pd

# --- CONFIGURATION PAGE WEB ---
st.set_page_config(page_title="DFM Europe - Pointeuse Web", page_icon="🕒", layout="wide")

CONTRAT_H_JOUR = 7.0

def calculate_worked_hours(arrival_str, departure_str, break_hours):
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

st.title("🕒 DFM Europe - Pointeuse de Travail")
st.caption("Chef de projet IoT - Saisie Rapide Hebdomadaire")

# --- NAVIGATION BARRE LATÉRALE ---
menu = st.sidebar.radio("Navigation", ["⚡ Saisie Semaine", "📊 Historique", "📂 Import Google Sheets"])

if menu == "⚡ Saisie Semaine":
    st.subheader("Saisie rapide du Lundi au Vendredi")
    
    today = datetime.date.today()
    monday = today - timedelta(days=today.weekday())
    
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
    data_list = []
    
    with st.form("form_semaine"):
        cols = st.columns([1.5, 2, 2, 2, 1.5, 3])
        cols[0].write("**Jour**")
        cols[1].write("**Date**")
        cols[2].write("**Arrivée**")
        cols[3].write("**Départ**")
        cols[4].write("**Pause (h)**")
        cols[5].write("**Commentaire**")
        
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
            
            data_list.append({
                "Date": dt.strftime("%Y-%m-%d"),
                "Arrivée": arr_str,
                "Départ": dep_str,
                "Pause": pause,
                "Durée Travaillée": worked,
                "H. Supp": overtime,
                "Commentaire": com
            })
            
        submitted = st.form_submit_button("💾 Enregistrer la semaine", use_container_width=True)
        if submitted:
            df = pd.DataFrame(data_list)
            st.success("✅ Semaine enregistrée avec succès !")
            st.dataframe(df, use_container_width=True)

elif menu == "📊 Historique":
    st.subheader("Récapitulatif des heures")
    st.info("Ici s'affichera le récapitulatif directement lié à votre base de données Google Sheets.")