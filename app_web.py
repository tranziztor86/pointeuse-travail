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

def get_french_holidays(year):
    """Calcule les jours fériés français (fixes et mobiles) pour une année."""
    holidays_dict = {
        datetime.date(year, 1, 1): "Jour de l'An",
        datetime.date(year, 5, 1): "Fête du Travail",
        datetime.date(year, 5, 8): "Victoire 1945",
        datetime.date(year, 7, 14): "Fête Nationale",
        datetime.date(year, 8, 15): "Assomption",
        datetime.date(year, 11, 1): "Toussaint",
        datetime.date(year, 11, 11): "Armistice 1918",
        datetime.date(year, 12, 25): "Noël",
    }
    # Algorithme de Meeus pour le calcul de Pâques
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    easter = datetime.date(year, month, day)
    
    holidays_dict[easter + timedelta(days=1)] = "Lundi de Pâques"
    holidays_dict[easter + timedelta(days=39)] = "Ascension"
    holidays_dict[easter + timedelta(days=50)] = "Lundi de Pentecôte"
    return holidays_dict

def get_cp_reference_start_date(today_date):
    """Détermine le 1er juin de la période de référence légale en cours."""
    if today_date.month >= 6:
        return datetime.date(today_date.year, 6, 1)
    else:
        return datetime.date(today_date.year - 1, 6, 1)

def calculate_earned_cp(start_ref_date, today_date, rate_per_month=2.0833):
    """Calcule le nombre de jours CP acquis depuis le 1er juin."""
    if today_date < start_ref_date:
        return 0.0
    months = (today_date.year - start_ref_date.year) * 12 + (today_date.month - start_ref_date.month) + 1
    months = min(max(months, 0), 12)
    return round(months * rate_per_month, 2)

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
st.caption("Chef de projet IoT - Saisie Rapide, Jours Fériés & Suivi Responsable")

# --- CONNEXION GOOGLE SHEETS ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"❌ Erreur de connexion à Google Sheets : {e}")
    st.stop()

# --- MENU LATÉRAL ---
menu = st.sidebar.radio(
    "Navigation", 
    ["⚡ Saisie Semaine", "🌴 Congés & Récupérations", "📊 Historique & Compteurs", "✉️ Informer mon Chef"]
)

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Paramètres CP")
mode_cp = st.sidebar.selectbox("Calcul CP", ["25 jours (Ouvrés : 2.08j/mois)", "30 jours (Ouvrables : 2.5j/mois)"])
cp_rate = 2.0833 if "25" in mode_cp else 2.5
cp_initial_stock = st.sidebar.number_input("Solde CP initial (Report N-1)", min_value=0.0, value=0.0, step=0.5)

# ==============================================================================
# MENU 1 : SAISIE SEMAINE
# ==============================================================================
if menu == "⚡ Saisie Semaine":
    st.subheader("⚡ Saisie rapide du Lundi au Vendredi")
    
    today = datetime.date.today()
    monday = today - timedelta(days=today.weekday())
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
    holidays = get_french_holidays(today.year)
    
    with st.form("form_semaine"):
        st.write("Ajustez vos horaires (les jours fériés sont pré-détectés) :")
        
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
            is_ferie = d_date in holidays
            nom_ferie = holidays.get(d_date, "")
            
            c = st.columns([1.5, 2, 2, 2, 1.5, 3])
            
            label_jour = f"**{day_name}** 🇫🇷" if is_ferie else f"**{day_name}**"
            c[0].write(label_jour)
            
            dt = c[1].date_input(f"date_{i}", value=d_date, label_visibility="collapsed")
            
            def_arr = datetime.time(0, 0) if is_ferie else datetime.time(8, 30)
            def_dep = datetime.time(0, 0) if is_ferie else datetime.time(16, 30)
            def_pause = 0.0 if is_ferie else 1.0
            def_com = f"🎉 Férié : {nom_ferie}" if is_ferie else ""
            
            arr = c[2].time_input(f"arr_{i}", value=def_arr, label_visibility="collapsed")
            dep = c[3].time_input(f"dep_{i}", value=def_dep, label_visibility="collapsed")
            pause = c[4].number_input(f"pause_{i}", value=def_pause, step=0.5, label_visibility="collapsed")
            com = c[5].text_input(f"com_{i}", value=def_com, key=f"com_{i}", label_visibility="collapsed")
            
            arr_str = arr.strftime("%H:%M")
            dep_str = dep.strftime("%H:%M")
            
            if is_ferie and arr_str == "00:00" and dep_str == "00:00":
                worked, overtime = 0.0, 0.0
            else:
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
                st.success("✅ Semaine enregistrée avec succès !")
                st.dataframe(new_df)
            except Exception as e:
                st.error(f"❌ Erreur lors de l'enregistrement : {e}")

# ==============================================================================
# MENU 2 : CONGÉS & RÉCUPÉRATIONS
# ==============================================================================
elif menu == "🌴 Congés & Récupérations":
    st.subheader("🌴 Déclaration de Congés, Récupérations & Absences")
    
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
            jours_deduits, heures_recup = 0.0, 0.0
            
        motif = st.text_input("Commentaire / Motif")
        submit_absence = st.form_submit_button("💾 Enregistrer l'événement")
        
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
                st.success(f"✅ Événement enregistré !")
                st.dataframe(new_abs)
            except Exception as e:
                st.error(f"❌ Erreur : {e}")

# ==============================================================================
# MENU 3 : HISTORIQUE & VUES PAR SEMAINE / MOIS / ANNÉE
# ==============================================================================
elif menu == "📊 Historique & Compteurs":
    st.subheader("📊 Historique Visuel & Compteurs")
    
    # Lecture des données Google Sheets
    try:
        df_p = conn.read(worksheet=WS_POINTAGES, ttl="0")
    except Exception:
        df_p = pd.DataFrame()

    try:
        df_a = conn.read(worksheet=WS_ABSENCES, ttl="0")
    except Exception:
        df_a = pd.DataFrame()

    # Compteurs légaux globaux
    today = datetime.date.today()
    ref_start = get_cp_reference_start_date(today)
    cp_earned_this_period = calculate_earned_cp(ref_start, today, rate_per_month=cp_rate)
    
    tot_overtime_gained = pd.to_numeric(df_p.get("H. Supp", 0), errors='coerce').sum() if df_p is not None and not df_p.empty else 0.0
    tot_overtime_used = pd.to_numeric(df_a.get("Heures Récup H.SUP", 0), errors='coerce').sum() if df_a is not None and not df_a.empty else 0.0
    tot_cp_used = pd.to_numeric(df_a.get("Jours CP", 0), errors='coerce').sum() if df_a is not None and not df_a.empty else 0.0
    
    solde_h_sup = tot_overtime_gained - tot_overtime_used
    total_cp_available = cp_initial_stock + cp_earned_this_period - tot_cp_used

    st.markdown("### 📈 Bilan Général des Soldes")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Solde Net H.SUP", f"{solde_h_sup:.2f} h", delta=f"+{tot_overtime_gained:.2f}h / -{tot_overtime_used:.2f}h")
    c2.metric("CP Acquis (Période)", f"{cp_earned_this_period:.2f} j")
    c3.metric("CP Posés", f"{tot_cp_used:.1f} j")
    c4.metric("Solde CP Disponible", f"{total_cp_available:.2f} j")

    st.markdown("---")
    
    # FILTRES DE VISUALISATION (Semaine / Mois / Année)
    st.markdown("### 🗓️ Filtrer l'Historique des Pointages")
    
    if df_p is not None and not df_p.empty:
        df_p['Date_dt'] = pd.to_datetime(df_p['Date'], errors='coerce')
        df_p['Année'] = df_p['Date_dt'].dt.year
        df_p['Mois'] = df_p['Date_dt'].dt.strftime('%Y-%m (%B)')
        df_p['Semaine'] = df_p['Date_dt'].dt.isocalendar().week.apply(lambda w: f"Semaine {w}")
        
        f_type = st.radio("Mode d'affichage :", ["Tout afficher", "Par Année", "Par Mois", "Par Semaine"], horizontal=True)
        
        df_filtered = df_p.copy()
        
        if f_type == "Par Année":
            annees = sorted(df_p['Année'].dropna().unique(), reverse=True)
            sel_a = st.selectbox("Sélectionnez l'année :", annees)
            df_filtered = df_p[df_p['Année'] == sel_a]
            
        elif f_type == "Par Mois":
            mois_list = sorted(df_p['Mois'].dropna().unique(), reverse=True)
            sel_m = st.selectbox("Sélectionnez le mois :", mois_list)
            df_filtered = df_p[df_p['Mois'] == sel_m]
            
        elif f_type == "Par Semaine":
            sem_list = sorted(df_p['Semaine'].dropna().unique(), reverse=True)
            sel_s = st.selectbox("Sélectionnez la semaine :", sem_list)
            df_filtered = df_p[df_p['Semaine'] == sel_s]

        # Résumé pour la période filtrée
        h_tot = pd.to_numeric(df_filtered["Durée Travaillée"], errors='coerce').sum()
        h_sup = pd.to_numeric(df_filtered["H. Supp"], errors='coerce').sum()
        
        st.info(f"📊 **Bilan Période Sélectionnée :** {h_tot:.2f} h travaillées au total | **+{h_sup:.2f} h** supplémentaires")
        
        # Graphique des heures travaillées
        st.write("**Graphique des heures quotidiennes :**")
        df_chart = df_filtered.set_index("Date")[["Durée Travaillée", "H. Supp"]]
        st.bar_chart(df_chart)

        # Tableau propre
        st.dataframe(df_filtered[["Date", "Heure Arrivée", "Heure Départ", "Pause (H)", "Durée Travaillée", "H. Supp", "Commentaire"]], use_container_width=True)

        # Bouton Téléchargement CSV pour le manager
        csv_data = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger ce bilan filtré (CSV/Excel)",
            data=csv_data,
            file_name=f"releve_heures_{datetime.date.today()}.csv",
            mime="text/csv",
        )
    else:
        st.info("Aucun pointage enregistré pour le moment.")

# ==============================================================================
# MENU 4 : INFORMER MON RESPONSABLE / CHEF DE PROJET
# ==============================================================================
elif menu == "✉️ Informer mon Chef":
    st.subheader("✉️ Transmettre mes heures à mon responsable")
    
    st.write("""
    Voici un résumé prêt à être transmis à votre chef de projet par **E-mail**, **Teams** ou **Slack**.
    """)
    
    # Lecture des données du mois en cours
    try:
        df_p = conn.read(worksheet=WS_POINTAGES, ttl="0")
    except Exception:
        df_p = pd.DataFrame()
        
    if df_p is not None and not df_p.empty:
        df_p['Date_dt'] = pd.to_datetime(df_p['Date'], errors='coerce')
        current_month = datetime.date.today().strftime('%Y-%m')
        df_m = df_p[df_p['Date_dt'].dt.strftime('%Y-%m') == current_month]
        
        tot_h_mois = pd.to_numeric(df_m["Durée Travaillée"], errors='coerce').sum()
        tot_h_sup_mois = pd.to_numeric(df_m["H. Supp"], errors='coerce').sum()
        nb_jours = len(df_m[df_m["Durée Travaillée"] > 0])
        
        email_template = f"""Bonjour,

Voici le récapitulatif de mes heures de travail pour le mois en cours ({datetime.date.today().strftime('%B %Y')}) :

• Nombre de jours travaillés : {nb_jours} jours
• Total heures effectuées : {tot_h_mois:.2f} heures
• Heures supplémentaires acquises : +{tot_h_sup_mois:.2f} heures

Le détail quotidien est enregistré sur ma feuille de pointage.

Bien cordialement,
Jeremy Landet
Chef de projet IoT
        """
        
        st.text_area("📋 Message type à copier-coller pour votre chef :", email_template, height=220)
        st.info("💡 Vous pouvez aussi télécharger l'export CSV dans l'onglet 'Historique' et l'ajouter en pièce jointe !")
    else:
        st.warning("Veuillez d'abord enregistrer des pointages pour générer un résumé.")
