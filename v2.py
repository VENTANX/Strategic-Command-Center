# ==============================================================================
# PROJECT: Command Center - Final, Complete and Stable Version
# Author: OUSSAMA ASLOUJ
# MODIFICATIONS: Complete overhaul of the Solar tab into a unified dashboard
# ==============================================================================
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter
import tkintermapview
import requests
import pandas as pd
import joblib
from datetime import datetime, timedelta, timezone
import webbrowser
import re
from shapely.geometry import Point, Polygon
import threading
import feedparser
import math

# --- NOUVELLES IMPORTATIONS POUR LES GRAPHIQUES ---
from collections import deque
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
matplotlib.use('TkAgg') # Spécifier le backend pour tkinter

# --- CONFIGURATION ---
RISK_ZONES = {
    "Site d'essais NK": Polygon([(41.4, 129.0), (41.4, 129.2), (41.2, 129.2), (41.2, 129.0)]),
    "Zone d'essais SLBM (Mer de Barents)": Polygon([(72.0, 35.0), (72.0, 40.0), (70.0, 40.0), (70.0, 35.0)]),
    "Zone d'essais SLBM (Mer du Japon)": Polygon([(40.0, 132.0), (40.0, 134.0), (38.0, 134.0), (38.0, 132.0)]),
    "Zone d'essais SLBM (Mer Jaune)": Polygon([(35.0, 123.0), (35.0, 125.0), (33.0, 125.0), (33.0, 123.0)])
}
GDACS_RSS_URL = "https://www.gdacs.org/rss.aspx"
NASA_API_KEY = "dOyFPhDlFaYMkH5obElJPIGmpU4pvcfiNmsSkgjJ"

customtkinter.set_appearance_mode("Dark")
customtkinter.set_default_color_theme("blue")

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Centre de Commandement et d'Analyse Stratégique")
        self.geometry("1600x900")
        
        self.is_playback_mode = False
        self.processed_event_ids = set()
        
        self.is_advanced_mode = tkinter.BooleanVar(value=False)
        self.seismic_time_series = deque(maxlen=50) 
        self.seismic_frequency = {} 

        try:
            self.seismic_model = joblib.load('anomaly_detector_model.joblib')
            self.seismic_scaler = joblib.load('data_scaler.joblib')
            self.tsunami_model = joblib.load('tsunami_predictor_model.joblib')
        except FileNotFoundError as e:
            messagebox.showerror("Erreur Critique", f"Fichier modèle introuvable : {e.filename}\nVeuillez lancer les scripts d'entraînement.")
            self.destroy(); return
        
        self.create_widgets()
        self.start_app()

    def create_widgets(self):
        self.tab_view = customtkinter.CTkTabview(self, width=1580, height=880)
        self.tab_view.pack(pady=10, padx=10, fill="both", expand=True)

        self.seismic_tab = self.tab_view.add("Moniteur Sismique")
        self.solar_tab = self.tab_view.add("Activité Solaire")
        self.asteroid_tab = self.tab_view.add("Menaces Orbitales")
        self.disaster_tab = self.tab_view.add("Alertes Catastrophes")

        self.setup_seismic_tab()
        self.setup_solar_tab()
        self.setup_asteroid_tab()
        self.setup_disaster_tab()

    def start_app(self):
        self.status_label.configure(text="SYNCHRONISATION INITIALE...", text_color="yellow")
        self.initial_seismic_load_complete = False
        threading.Thread(target=self.initial_data_seed, daemon=True).start()

    def initial_data_seed(self):
        print("Synchronisation initiale des événements sismiques...")
        try:
            url = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson'
            response = requests.get(url, timeout=10); response.raise_for_status()
            initial_data = response.json()
            for event in initial_data['features']: self.processed_event_ids.add(event['id'])
            print(f"{len(initial_data['features'])} événements existants ont été mémorisés.")
        except requests.exceptions.RequestException as e: print(f"Erreur durant la synchronisation initiale: {e}")
        self.initial_seismic_load_complete = True
        self.after(0, self.start_live_updates)

    def start_live_updates(self):
        self.status_label.configure(text="MODE: DIRECT", text_color="green")
        print("Système en mode surveillance directe.")
        self.update_seismic_data()
        self.update_solar_data()
        self.update_asteroid_data()
        self.update_disaster_data()

    # ==================== MODULE SISMIQUE ====================
    def setup_seismic_tab(self):
        control_frame = customtkinter.CTkFrame(self.seismic_tab, height=80); control_frame.pack(side="top", fill="x", padx=10, pady=(10,5))
        customtkinter.CTkLabel(control_frame, text="Mode Relecture :", font=customtkinter.CTkFont(weight="bold")).pack(side="left", padx=(10,5))
        self.year_entry = customtkinter.CTkEntry(control_frame, placeholder_text="AAAA", width=60); self.year_entry.pack(side="left", padx=2)
        self.month_entry = customtkinter.CTkEntry(control_frame, placeholder_text="MM", width=40); self.month_entry.pack(side="left", padx=2)
        self.day_entry = customtkinter.CTkEntry(control_frame, placeholder_text="JJ", width=40); self.day_entry.pack(side="left", padx=2)
        customtkinter.CTkButton(control_frame, text="Lancer Relecture", command=self.start_playback).pack(side="left", padx=10)
        customtkinter.CTkButton(control_frame, text="Retour au Direct", command=self.stop_playback).pack(side="left", padx=2)
        customtkinter.CTkButton(control_frame, text="Générer SITREP", command=self.generate_sitrep_window).pack(side="left", padx=20)
        self.status_label = customtkinter.CTkLabel(control_frame, text="INITIALISATION...", text_color="yellow", font=customtkinter.CTkFont(weight="bold")); self.status_label.pack(side="right", padx=20)
        advanced_switch = customtkinter.CTkSwitch(control_frame, text="Mode Avancé", variable=self.is_advanced_mode, command=self.toggle_advanced_mode); advanced_switch.pack(side="right", padx=20)
        main_frame = customtkinter.CTkFrame(self.seismic_tab, fg_color="transparent"); main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.data_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent"); self.data_frame.pack(side="left", fill="both", expand=True)
        map_frame = customtkinter.CTkFrame(self.data_frame); map_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        list_frame = customtkinter.CTkFrame(self.data_frame, width=420); list_frame.pack(side="right", fill="y", expand=False, padx=(5, 0))
        customtkinter.CTkLabel(list_frame, text="Journal des Détections", font=customtkinter.CTkFont(size=16, weight="bold")).pack(pady=10)
        self.map_widget = tkintermapview.TkinterMapView(map_frame, corner_radius=0); self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=19); self.map_widget.pack(fill="both", expand=True); self.draw_risk_zones()
        style = ttk.Style(); style.theme_use("default"); style.configure("Treeview", background="#2a2d2e", foreground="white", fieldbackground="#2a2d2e", borderwidth=0); style.map('Treeview', background=[('selected', '#22559b')]); style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat"); style.map("Treeview.Heading", background=[('active', '#3484F0')])
        self.seismic_log = ttk.Treeview(list_frame, columns=('Time', 'Mag', 'Depth', 'Status'), show='headings'); self.seismic_log.heading('Time', text='Heure'); self.seismic_log.column('Time', width=80, anchor='center'); self.seismic_log.heading('Mag', text='Mag.'); self.seismic_log.column('Mag', width=50, anchor='center'); self.seismic_log.heading('Depth', text='Prof.'); self.seismic_log.column('Depth', width=50, anchor='center'); self.seismic_log.heading('Status', text='Statut'); self.seismic_log.column('Status', width=180, anchor='w'); self.seismic_log.pack(fill="both", expand=True, padx=5, pady=5); self.seismic_log.tag_configure('normal', foreground='#00FF00'); self.seismic_log.tag_configure('low_anomaly', foreground='orange'); self.seismic_log.tag_configure('high_anomaly', foreground='red', font=('Calibri', 10, 'bold')); self.seismic_log.tag_configure('critical_anomaly', foreground='magenta', font=('Calibri', 10, 'bold', 'underline')); self.seismic_log.tag_configure('tsunami_risk', foreground='cyan', font=('Calibri', 10, 'bold')); self.seismic_log.tag_configure('slbm_anomaly', foreground='#FF69B4', font=('Calibri', 10, 'bold'))
        self.graphs_frame = customtkinter.CTkFrame(main_frame, width=400)
        self.fig1, self.ax1 = plt.subplots(facecolor='#242424'); self.ax1.set_facecolor('#242424'); self.ax1.tick_params(axis='x', colors='white'); self.ax1.tick_params(axis='y', colors='white'); self.ax1.spines['bottom'].set_color('white'); self.ax1.spines['left'].set_color('white'); self.ax1.spines['top'].set_color('#242424'); self.ax1.spines['right'].set_color('#242424')
        self.canvas1 = FigureCanvasTkAgg(self.fig1, master=self.graphs_frame); self.canvas1.get_tk_widget().pack(fill="both", expand=True, pady=(10,5), padx=10)
        self.fig2, self.ax2 = plt.subplots(facecolor='#242424'); self.ax2.set_facecolor('#242424'); self.ax2.tick_params(axis='x', colors='white'); self.ax2.tick_params(axis='y', colors='white'); self.ax2.spines['bottom'].set_color('white'); self.ax2.spines['left'].set_color('white'); self.ax2.spines['top'].set_color('#242424'); self.ax2.spines['right'].set_color('#242424')
        self.canvas2 = FigureCanvasTkAgg(self.fig2, master=self.graphs_frame); self.canvas2.get_tk_widget().pack(fill="both", expand=True, pady=5, padx=10)
    
    def toggle_advanced_mode(self):
        if self.is_advanced_mode.get():
            self.data_frame.pack_configure(side="left", fill="both", expand=True); self.graphs_frame.pack(side="right", fill="y", expand=False, padx=(5, 0))
            self.seismic_time_series.clear(); self.seismic_frequency.clear(); self.update_graphs()
        else: self.graphs_frame.pack_forget()
        threading.Thread(target=self.update_seismic_data, daemon=True).start()

    def update_graphs(self):
        if not self.is_advanced_mode.get(): return
        self.ax1.cla()
        if self.seismic_time_series: times, mags = zip(*self.seismic_time_series); self.ax1.plot(times, mags, marker='o', linestyle='-', color='cyan', markersize=4)
        self.ax1.set_title("Magnitude (50 derniers événements)", color='white', fontsize=10); self.ax1.set_ylabel("Magnitude", color='white', fontsize=8); self.fig1.autofmt_xdate(); self.fig1.tight_layout(pad=2.0); self.canvas1.draw()
        self.ax2.cla()
        ten_minutes_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
        self.seismic_frequency = {t: c for t, c in self.seismic_frequency.items() if t > ten_minutes_ago.timestamp()}
        if self.seismic_frequency:
            sorted_times = sorted(self.seismic_frequency.keys()); labels = [datetime.fromtimestamp(t, tz=timezone.utc).strftime('%H:%M') for t in sorted_times]; counts = [self.seismic_frequency[t] for t in sorted_times]
            self.ax2.bar(labels, counts, color='orange')
        self.ax2.set_title("Fréquence par minute (10 min)", color='white', fontsize=10); self.ax2.set_ylabel("Nb. d'événements", color='white', fontsize=8); plt.setp(self.ax2.get_xticklabels(), rotation=45, ha="right"); self.fig2.tight_layout(pad=2.0); self.canvas2.draw()
        self.after(2000, self.update_graphs)

    def update_seismic_data(self):
        seismic_update_interval = 15000 if self.is_advanced_mode.get() else 60000
        if self.is_playback_mode: self.after(seismic_update_interval, self.update_seismic_data); return
        try:
            url = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson'
            response = requests.get(url, timeout=10); response.raise_for_status()
            live_data = response.json(); new_event_count = 0
            for event in reversed(live_data['features']):
                if event['id'] not in self.processed_event_ids: new_event_count += 1; self.processed_event_ids.add(event['id']); self.process_single_seismic_event(event)
            if new_event_count > 0: print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Traitement de {new_event_count} nouvel(s) événement(s) sismique(s).")
        except requests.exceptions.RequestException as e: print(f"Erreur API Sismique: {e}")
        self.after(seismic_update_interval, self.update_seismic_data)

    def process_single_seismic_event(self, event, is_playback=False):
        properties, geometry = event['properties'], event['geometry']
        mag, depth, lat, lon = properties.get('mag'), geometry['coordinates'][2], geometry['coordinates'][1], geometry['coordinates'][0]
        if mag is None or depth is None or mag < 0: return
        if self.is_advanced_mode.get() and not is_playback:
            event_time = datetime.fromtimestamp(properties['time'] / 1000, tz=timezone.utc); self.seismic_time_series.append((event_time, mag))
            current_minute = event_time.replace(second=0, microsecond=0).timestamp(); self.seismic_frequency[current_minute] = self.seismic_frequency.get(current_minute, 0) + 1
        place_str = properties.get('place');
        if not place_str or place_str == "null": place_str = f"Coordonnées: {lat:.2f}, {lon:.2f}"
        features_anomaly = pd.DataFrame([[depth, mag]], columns=['Depth', 'Magnitude']); features_anomaly_scaled = self.seismic_scaler.transform(features_anomaly)
        anomaly_score = self.seismic_model.decision_function(features_anomaly_scaled)[0]
        features_tsunami = pd.DataFrame([[depth, mag]], columns=['EQ_DEPTH', 'EQ_MAGNITUDE']); tsunami_proba = self.tsunami_model.predict_proba(features_tsunami)[0][1]
        is_tsunami_risk = (tsunami_proba > 0.70 and mag > 7.5); tsunami_risk_text = f" (Tsunami Prob. {tsunami_proba:.0%})" if is_tsunami_risk else ""
        zone = self.is_in_risk_zone(lat, lon); status, color, tag, alert, yield_info = f"Normal{tsunami_risk_text}", "green", "normal", False, ""; alert_title, alert_message = "", ""
        if anomaly_score < -0.01:
            estimated_yield = self.estimate_yield(mag); yield_info = f"\nPuissance Estimée: {estimated_yield}"
            if zone:
                if "SLBM" in zone: status, color, tag, alert_title, alert_message, alert = f"ANOMALIE ({zone})", "#FF69B4", "slbm_anomaly", "Alerte de Lancement Potentiel", f"Signature anormale détectée dans une zone d'essais SLBM connue: {zone} !", True
                else: status, color, tag, alert_title, alert_message, alert = f"CRITIQUE ({zone})", "magenta", "critical_anomaly", "ALERTE CRITIQUE GÉOPOLITIQUE", f"Anomalie forte détectée DANS une zone à haut risque: {zone} !", True
            elif anomaly_score < -0.1: status, color, tag, alert_title, alert_message, alert = "Anomalie Stratégique (Signature Artificielle)", "red", "high_anomaly", "Alerte de Sécurité", "Une signature sismique fortement anormale a été détectée, potentiellement artificielle.", True
            else: status, color, tag = "Anomalie Faible", "orange", "low_anomaly"
        elif is_tsunami_risk: status, color, tag, alert_title, alert_message, alert = f"Normal (RISQUE TSUNAMI)", "cyan", "tsunami_risk", "ALERTE TSUNAMI", "Un séisme avec un fort potentiel tsunamigène a été détecté.", True
        if is_tsunami_risk and status.startswith("Normal"): tag = "tsunami_risk"
        details = {'place': place_str, 'time': datetime.fromtimestamp(properties['time']/1000).strftime('%Y-%m-%d %H:%M:%S'), 'mag': f"{mag:.1f}", 'depth': f"{depth:.1f}", 'status': status, 'url': properties.get('url'), 'yield': yield_info.replace('\n', '')}
        marker = self.map_widget.set_marker(lat, lon, text=f"M{details['mag']}", marker_color_circle=color, command=self.on_marker_click_seismic); marker.data = details
        log_entry = (details['time'].split(' ')[1], details['mag'], details['depth'], status); self.seismic_log.insert('', 'end', values=log_entry, tags=(tag,)); self.seismic_log.yview_moveto(1)
        try:
            radius_km = self.calculate_radius_from_magnitude(mag)
            if radius_km > 0.5: self.map_widget.set_polygon(self.calculate_circle_points(lat, lon, radius_km), fill_color=color, outline_color=color, border_width=1, name=f"radius_{event['id']}")
        except Exception as e: print(f"Erreur lors de la création du polygone de rayon : {e}")
        if status != "Normal": marker.final_color = color; self.pulse_marker(marker)
        if alert and not is_playback and self.initial_seismic_load_complete: messagebox.showwarning(alert_title, f"{alert_message}\n\nLieu: {details['place']}{yield_info}")
    
    def generate_sitrep_window(self):
        win = customtkinter.CTkToplevel(self); win.title("Rapport de Situation (SITREP)"); win.geometry("700x800")
        report_text = self.generate_sitrep_text()
        textbox = customtkinter.CTkTextbox(win, wrap="word", font=customtkinter.CTkFont(family="monospace", size=13)); textbox.pack(fill="both", expand=True, padx=10, pady=10); textbox.insert("0.0", report_text); textbox.configure(state="disabled")
        def copy_to_clipboard(): self.clipboard_clear(); self.clipboard_append(report_text); messagebox.showinfo("Copié", "Le rapport a été copié.")
        customtkinter.CTkButton(win, text="Copier dans le presse-papiers", command=copy_to_clipboard).pack(pady=10)

    def generate_sitrep_text(self):
        report = []; nl = "\n"; report.append("*"*20 + " RAPPORT DE SITUATION STRATÉGIQUE " + "*"*20); report.append(f"Généré le: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"); report.append("="*67 + nl)
        report.append("1. DOMAINE SISMIQUE:"); seismic_alerts = []
        for item_id in self.seismic_log.get_children():
            if any(tag in self.seismic_log.item(item_id, 'tags') for tag in ['high_anomaly', 'critical_anomaly', 'tsunami_risk', 'slbm_anomaly']): values = self.seismic_log.item(item_id, 'values'); seismic_alerts.append(f"   - ALERTE: {values[3]} (Mag {values[1]}) détecté à {values[0]} UTC.")
        if seismic_alerts: report.extend(seismic_alerts)
        else: report.append("   - Aucune alerte de haut niveau active.")
        report.append(nl); report.append("2. DOMAINE SOLAIRE:")
        # --- MODIFICATION : Récupération des données depuis les widgets du nouveau tableau de bord ---
        try:
            report.append(f"   - Probabilité Éruption (24h) -> Classe M: {self.m_prob_val}%, Classe X: {self.x_prob_val}%")
            report.append(f"   - {self.cme_summary_label.cget('text')}")
        except AttributeError: report.append("   - Données solaires non encore chargées.")
        report.append(nl); report.append("3. DOMAINE ORBITAL:"); high_risk_asteroids = []
        for item_id in self.asteroid_log.get_children():
            if 'high_risk' in self.asteroid_log.item(item_id, 'tags'): values = self.asteroid_log.item(item_id, 'values'); high_risk_asteroids.append(f"   - ALERTE RISQUE ÉLEVÉ: Objet '{values[1]}' en approche le {values[0]}.")
        if high_risk_asteroids: report.extend(high_risk_asteroids)
        else: report.append("   - Aucune menace orbitale à haut risque détectée.")
        report.append(nl); report.append("4. DOMAINE CATASTROPHES (GDACS):"); gdacs_alerts = []
        for item_id in self.disaster_log.get_children():
            if any(tag in self.disaster_log.item(item_id, 'tags') for tag in ['Red', 'Orange']):
                values = self.disaster_log.item(item_id, 'values'); gdacs_alerts.append(f"   - ALERTE {values[3].upper()}: {values[1]} en {values[2]}.")
        if gdacs_alerts: report.extend(gdacs_alerts)
        else: report.append("   - Aucune alerte GDACS orange ou rouge active.")
        report.append(nl); report.append("*"*30 + " FIN DU RAPPORT " + "*"*30); return "\n".join(report)
        
    def draw_risk_zones(self):
        self.map_widget.set_position(41.3, 129.1); self.map_widget.set_zoom(7)
        for name, polygon in RISK_ZONES.items():
            color = "#FF69B4" if "SLBM" in name else "red"
            self.map_widget.set_polygon(list(polygon.exterior.coords), outline_color=color, border_width=2, fill_color="", name=name)

    def calculate_radius_from_magnitude(self, m): return 2**m
    def calculate_circle_points(self, lat, lon, r_km, num_pts=25):
        pts, r_earth, lat_r, lon_r = [], 6371.0, math.radians(lat), math.radians(lon)
        for i in range(num_pts + 1):
            ang = math.radians(i * (360/num_pts)); end_lat_r = math.asin(math.sin(lat_r)*math.cos(r_km/r_earth) + math.cos(lat_r)*math.sin(r_km/r_earth)*math.cos(ang)); end_lon_r = lon_r + math.atan2(math.sin(ang)*math.sin(r_km/r_earth)*math.cos(lat_r), math.cos(r_km/r_earth)-math.sin(lat_r)*math.sin(end_lat_r)); pts.append((math.degrees(end_lat_r), math.degrees(end_lon_r)))
        return pts
    def on_marker_click_seismic(self, marker):
        details = marker.data; win = customtkinter.CTkToplevel(self); win.title("Détails de l'Événement Sismique"); win.geometry("450x220")
        text = (f"Lieu: {details['place']}\n" f"Date/Heure (UTC): {details['time']}\n" f"Magnitude: {details['mag']} | Profondeur: {details['depth']} km\n" f"Statut du modèle: {details['status']}\n" f"{details.get('yield', '')}")
        customtkinter.CTkLabel(win, text=text, justify=tkinter.LEFT, wraplength=430).pack(pady=10, padx=10, fill="both", expand=True); customtkinter.CTkButton(win, text="Ouvrir sur le site de l'USGS", command=lambda: webbrowser.open_new_tab(details['url'])).pack(pady=10)
    def is_in_risk_zone(self, lat, lon): point = Point(lon, lat); return next((name for name, zone in RISK_ZONES.items() if zone.contains(point)), None)
    def estimate_yield(self, magnitude):
        try: yield_kt = 10**(1.25 * magnitude - 5.5); return f"~{yield_kt * 1000:.0f} tonnes" if yield_kt < 1 else f"~{yield_kt:.1f} kilotonnes"
        except: return "N/A"
    def pulse_marker(self, marker, steps=10):
        try:
            if steps > 0: marker.set_marker_color_circle("white" if marker.marker_color_circle != "white" else marker.final_color); self.after(150, lambda: self.pulse_marker(marker, steps - 1))
            else: marker.set_marker_color_circle(marker.final_color)
        except Exception: pass
    def start_playback(self):
        try: start_time = datetime(int(self.year_entry.get()), int(self.month_entry.get()), int(self.day_entry.get())); end_time = start_time + timedelta(days=1)
        except ValueError: messagebox.showerror("Erreur de Date", "Veuillez entrer une date valide (AAAA, MM, JJ)."); return
        self.is_playback_mode = True; self.status_label.configure(text="MODE: RELECTURE", text_color="orange"); self.seismic_log.delete(*self.seismic_log.get_children()); self.map_widget.delete_all_marker(); self.map_widget.delete_all_polygon(); self.draw_risk_zones()
        try:
            url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={start_time.strftime('%Y-%m-%d')}&endtime={end_time.strftime('%Y-%m-%d')}"; response = requests.get(url, timeout=20); response.raise_for_status()
            events = sorted(response.json()['features'], key=lambda e: e['properties']['time'])
            if events: self.playback_next_event(events, 0)
            else: messagebox.showinfo("Info", "Aucun événement trouvé pour cette date."); self.stop_playback()
        except Exception as e: messagebox.showerror("Erreur API", f"Impossible de récupérer les données historiques: {e}"); self.stop_playback()
    def playback_next_event(self, events, index):
        if index >= len(events) or not self.is_playback_mode: self.stop_playback(); return
        self.process_single_seismic_event(events[index], is_playback=True); self.after(500, lambda: self.playback_next_event(events, index + 1))
    def stop_playback(self): self.is_playback_mode = False; self.status_label.configure(text="SYNCHRONISANT...", text_color="yellow"); self.map_widget.delete_all_marker(); self.map_widget.delete_all_polygon(); self.draw_risk_zones(); self.seismic_log.delete(*self.seismic_log.get_children()); self.initial_seismic_load_complete = False; threading.Thread(target=self.initial_data_seed, daemon=True).start()
    
    # ==================== MODULE SOLAIRE (REFONTE TOTALE) ====================
    def setup_solar_tab(self):
        # --- Cadre principal du tableau de bord ---
        main_frame = customtkinter.CTkFrame(self.solar_tab, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # --- Panneau Supérieur "At-a-Glance" ---
        top_panel = customtkinter.CTkFrame(main_frame)
        top_panel.pack(side="top", fill="x", pady=(0, 10))

        # Sous-panneau pour les jauges
        gauge_panel = customtkinter.CTkFrame(top_panel)
        gauge_panel.pack(side="left", padx=20, pady=10)
        customtkinter.CTkLabel(gauge_panel, text="Probabilité d'Éruption (24h)", font=customtkinter.CTkFont(size=16, weight="bold")).pack(pady=(0,10))
        
        prob_frame = customtkinter.CTkFrame(gauge_panel, fg_color="transparent")
        prob_frame.pack()
        self.m_class_gauge = tkinter.Canvas(prob_frame, width=150, height=150, bg="#2a2d2e", highlightthickness=0)
        self.m_class_gauge.pack(side="left", padx=20)
        self.x_class_gauge = tkinter.Canvas(prob_frame, width=150, height=150, bg="#2a2d2e", highlightthickness=0)
        self.x_class_gauge.pack(side="left", padx=20)
        
        # Sous-panneau pour le résumé CME
        cme_summary_panel = customtkinter.CTkFrame(top_panel)
        cme_summary_panel.pack(side="left", expand=True, fill="both", padx=20, pady=10)
        customtkinter.CTkLabel(cme_summary_panel, text="État des Menaces CME", font=customtkinter.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10)
        self.cme_summary_label = customtkinter.CTkLabel(cme_summary_panel, text="CMEs en transit vers la Terre : --", font=customtkinter.CTkFont(size=18), justify="left")
        self.cme_summary_label.pack(anchor="w", padx=10, pady=5)
        self.cme_eta_label = customtkinter.CTkLabel(cme_summary_panel, text="Prochain impact estimé : --", font=customtkinter.CTkFont(size=18), justify="left")
        self.cme_eta_label.pack(anchor="w", padx=10, pady=5)

        # --- Panneau Inférieur avec onglets pour les journaux détaillés ---
        log_tab_view = customtkinter.CTkTabview(main_frame, height=400)
        log_tab_view.pack(side="bottom", fill="both", expand=True)
        
        cme_tab = log_tab_view.add("Prévisions CME")
        flare_tab = log_tab_view.add("Journal des Éruptions (48h)")
        
        # Journal CME
        self.solar_cme_log = ttk.Treeview(cme_tab, columns=('StartTime', 'ArrivalTime', 'Speed', 'Risk'), show='headings')
        self.solar_cme_log.heading('StartTime', text='Heure de Départ (UTC)'); self.solar_cme_log.column('StartTime', width=200); self.solar_cme_log.heading('ArrivalTime', text="Heure d'Arrivée Estimée (UTC)"); self.solar_cme_log.column('ArrivalTime', width=200); self.solar_cme_log.heading('Speed', text='Vitesse (km/s)'); self.solar_cme_log.column('Speed', width=120, anchor='center'); self.solar_cme_log.heading('Risk', text='Risque Tempête'); self.solar_cme_log.column('Risk', width=150, anchor='center'); self.solar_cme_log.pack(fill="both", expand=True, padx=5, pady=5); self.solar_cme_log.tag_configure('High', foreground='red', font=('Calibri', 11, 'bold')); self.solar_cme_log.tag_configure('Moderate', foreground='orange')

        # Journal des éruptions
        self.solar_flare_log = ttk.Treeview(flare_tab, columns=('Time', 'Class', 'Region', 'Geo-effective'), show='headings'); self.solar_flare_log.heading('Time', text='Heure Début (UTC)'); self.solar_flare_log.heading('Class', text='Classe'); self.solar_flare_log.heading('Region', text='Région Solaire'); self.solar_flare_log.heading('Geo-effective', text='Menace Terre?'); self.solar_flare_log.column('Geo-effective', anchor='center'); self.solar_flare_log.pack(fill="both", expand=True, padx=5, pady=5); self.solar_flare_log.tag_configure('geoeffective_x', foreground='red', font=('Calibri', 12, 'bold')); self.solar_flare_log.tag_configure('geoeffective_m', foreground='orange', font=('Calibri', 11, 'bold'))
        
        # Initialiser les jauges
        self.draw_gauge(self.m_class_gauge, 0, "Classe M", "orange")
        self.draw_gauge(self.x_class_gauge, 0, "Classe X", "red")

    def draw_gauge(self, canvas, percentage, name, color):
        canvas.delete("all")
        size = 150
        padding = 15
        
        # Fond de la jauge
        canvas.create_arc(padding, padding, size-padding, size-padding, start=0, extent=359.9, style=tkinter.ARC, outline="#424242", width=12)
        
        # Jauge de pourcentage
        if percentage > 0:
            canvas.create_arc(padding, padding, size-padding, size-padding, start=90, extent=-(percentage * 3.6), style=tkinter.ARC, outline=color, width=12)
        
        # Texte
        canvas.create_text(size/2, size/2, text=f"{percentage}%", font=("Roboto", 24, "bold"), fill=color)
        canvas.create_text(size/2, size/2 + 30, text=name, font=("Roboto", 12), fill="white")

    def update_solar_data(self):
        if self.is_playback_mode: self.after(1800000, self.update_solar_data); return
        threading.Thread(target=self.update_solar_flare_log_data, daemon=True).start()
        threading.Thread(target=self.update_solar_cme_data, daemon=True).start()
        threading.Thread(target=self.update_flare_probability_data, daemon=True).start()
        self.after(1800000, self.update_solar_data)

    def update_solar_flare_log_data(self):
        try:
            end_date, start_date = datetime.utcnow(), datetime.utcnow() - timedelta(days=2); url=f"https://api.nasa.gov/DONKI/FLR?startDate={start_date.strftime('%Y-%m-%d')}&endDate={end_date.strftime('%Y-%m-%d')}&api_key={NASA_API_KEY}"
            flares=requests.get(url, timeout=10).json(); self.after(0, self.populate_solar_flare_log, flares)
        except Exception as e: print(f"Erreur API Solaire (FLR): {e}")
    
    def populate_solar_flare_log(self, flares):
        self.solar_flare_log.delete(*self.solar_flare_log.get_children())
        for flare in reversed(flares):
            c_type = flare.get('classType', 'N/A')
            is_geo=self.is_flare_geoeffective(flare.get('sourceLocation')); geo_text="OUI" if is_geo else "Non"; tag='normal'
            if is_geo and (c_type.startswith('X') or c_type.startswith('M')): tag='geoeffective_x' if c_type.startswith('X') else 'geoeffective_m'
            self.solar_flare_log.insert('', 'end', values=(flare.get('beginTime', 'N/A'), c_type, flare.get('sourceLocation', 'N/A'), geo_text), tags=(tag,))

    def update_solar_cme_data(self):
        try:
            start_date=datetime.utcnow(); end_date=start_date+timedelta(days=7); url=f"https://api.nasa.gov/DONKI/CMEAnalysis?startDate={start_date.strftime('%Y-%m-%d')}&endDate={end_date.strftime('%Y-%m-%d')}&mostAccurateOnly=true&api_key={NASA_API_KEY}"
            analyses=requests.get(url, timeout=15).json(); self.after(0, self.populate_solar_cme_log, analyses)
        except Exception as e: print(f"Erreur API Solaire (CME): {e}")

    def populate_solar_cme_log(self, analyses):
        self.solar_cme_log.delete(*self.solar_cme_log.get_children())
        cme_count = 0; next_eta = "Aucun"
        earth_bound_cmes = []
        for analysis in analyses:
            if analysis.get('isMostAccurate') and analysis.get('enlil') and analysis['enlil']['estimatedShockArrivalTime']:
                earth_bound_cmes.append(analysis)
        
        cme_count = len(earth_bound_cmes)
        if cme_count > 0:
            earth_bound_cmes.sort(key=lambda x: x['enlil']['estimatedShockArrivalTime'])
            next_eta = earth_bound_cmes[0]['enlil']['estimatedShockArrivalTime'].replace('T', ' ').replace('Z', ' UTC')
            for analysis in earth_bound_cmes:
                start_time = analysis.get('time21_5', 'N/A').replace('T', ' ').replace('Z', ''); arrival_time = analysis['enlil']['estimatedShockArrivalTime'].replace('T', ' ').replace('Z', ''); speed = analysis['enlil']['speed']
                risk, tag = "N/A", "normal";
                if float(speed) > 800: risk, tag = "Élevé", "High"
                elif float(speed) > 500: risk, tag = "Modéré", "Moderate"
                else: risk, tag = "Faible", "normal"
                self.solar_cme_log.insert('', 'end', values=(start_time, arrival_time, speed, risk), tags=(tag,))
        
        self.cme_summary_label.configure(text=f"CMEs en transit vers la Terre : {cme_count}")
        self.cme_eta_label.configure(text=f"Prochain impact estimé : {next_eta}")

    def update_flare_probability_data(self):
        try:
            url=f"https://api.nasa.gov/DONKI/SFP?startDate={datetime.utcnow().strftime('%Y-%m-%d')}&endDate={datetime.utcnow().strftime('%Y-%m-%d')}&api_key={NASA_API_KEY}"
            preds = requests.get(url, timeout=10).json()
            if preds: self.after(0, self.populate_flare_probability, preds[-1])
        except Exception as e: print(f"Erreur API Solaire (SFP): {e}")
    
    def populate_flare_probability(self, last_pred):
        m_prob, x_prob = 0, 0
        for p in last_pred.get('predictions', []):
            if p.get('classType') == 'M-class': m_prob = p.get('probability', 0)
            if p.get('classType') == 'X-class': x_prob = p.get('probability', 0)
        
        # Stocker les valeurs pour le SITREP
        self.m_prob_val = m_prob
        self.x_prob_val = x_prob
        
        self.draw_gauge(self.m_class_gauge, m_prob, "Classe M", "orange")
        self.draw_gauge(self.x_class_gauge, x_prob, "Classe X", "red")

    def is_flare_geoeffective(self, location_string):
        if not location_string: return False
        match=re.search(r'[EW](\d+)', location_string.upper()); return match and int(match.group(1)) < 60

    # --- Fonctions restantes ---
    def setup_asteroid_tab(self):
        summary_frame = customtkinter.CTkFrame(self.asteroid_tab, fg_color="transparent"); summary_frame.pack(fill="x", padx=10, pady=10); self.asteroid_summary_label1 = customtkinter.CTkLabel(summary_frame, text="Approche la plus Proche: --", font=customtkinter.CTkFont(size=15, weight="bold")); self.asteroid_summary_label1.pack(side="left", padx=20); self.asteroid_summary_label2 = customtkinter.CTkLabel(summary_frame, text="Objet le plus Large: --", font=customtkinter.CTkFont(size=15, weight="bold")); self.asteroid_summary_label2.pack(side="left", padx=20); self.asteroid_summary_label3 = customtkinter.CTkLabel(summary_frame, text="Alertes de Risque Élevé: --", font=customtkinter.CTkFont(size=15, weight="bold")); self.asteroid_summary_label3.pack(side="left", padx=20)
        list_frame = customtkinter.CTkFrame(self.asteroid_tab, fg_color="transparent"); list_frame.pack(fill="both", expand=True, padx=10, pady=0); self.asteroid_log=ttk.Treeview(list_frame, columns=('Date', 'Name', 'Diameter', 'Distance', 'Risk'), show='headings'); self.asteroid_log.heading('Date', text='Date Passage'); self.asteroid_log.column('Date', width=180); self.asteroid_log.heading('Name', text='Nom Objet'); self.asteroid_log.column('Name', width=180); self.asteroid_log.heading('Diameter', text='Diamètre Est. (m)'); self.asteroid_log.column('Diameter', width=150, anchor='center'); self.asteroid_log.heading('Distance', text='Distance Passage (km)'); self.asteroid_log.column('Distance', width=180, anchor='center'); self.asteroid_log.heading('Risk', text='Score Risque'); self.asteroid_log.column('Risk', width=100, anchor='center'); self.asteroid_log.pack(fill="both", expand=True, padx=5, pady=5); self.asteroid_log.tag_configure('low_risk', foreground='yellow'); self.asteroid_log.tag_configure('medium_risk', foreground='orange'); self.asteroid_log.tag_configure('high_risk', foreground='red', font=('Calibri', 10, 'bold'))
    def calculate_risk_score(self, d_m, dist_km):
        score=0
        if d_m > 25 and dist_km < 7500000: score+=1
        if d_m > 140: score+=1
        if dist_km < 384400 * 2: score+=1
        if dist_km < 384400: score+=2
        if score >= 4: return "Élevé", "high_risk"
        if score >= 2: return "Modéré", "medium_risk"
        if score > 0: return "Faible", "low_risk"
        return "Nul", "normal"
    def update_asteroid_data(self):
        if self.is_playback_mode: self.after(3600000, self.update_asteroid_data); return
        try:
            url="https://ssd-api.jpl.nasa.gov/cad.api?dist-max=20LD&sort=dist"; asteroids=requests.get(url, timeout=15).json(); self.asteroid_log.delete(*self.asteroid_log.get_children())
            close_name, large_name = "--", "--"; close_dist, large_diam, high_risk_count = float('inf'), 0, 0
            if int(asteroids.get('count', 0)) > 0:
                for data in asteroids['data']:
                    data_map={f: v for f, v in zip(asteroids['fields'], data)}; dist_km=float(data_map.get('dist', 0))*149597870.7; h_mag=float(data_map.get('h', 25)); d_m=(1329/(10**(0.2 * h_mag)))*1000 if h_mag > 0 else 0
                    if dist_km < close_dist: close_dist, close_name = dist_km, data_map.get('des')
                    if d_m > large_diam: large_diam, large_name = d_m, data_map.get('des')
                    risk_text, risk_tag=self.calculate_risk_score(d_m, dist_km)
                    if risk_tag == "high_risk": high_risk_count += 1
                    self.asteroid_log.insert('', 'end', values=(data_map.get('cd'), data_map.get('des'), f"{d_m:.0f}", f"{dist_km:,.0f}", risk_text), tags=(risk_tag,))
            self.asteroid_summary_label1.configure(text=f"Approche la plus Proche: {close_name} ({close_dist:,.0f} km)"); self.asteroid_summary_label2.configure(text=f"Objet le plus Large: {large_name} (~{large_diam:.0f} m)"); self.asteroid_summary_label3.configure(text=f"Alertes de Risque Élevé: {high_risk_count}")
        except Exception as e: print(f"Erreur API Astéroïdes: {e}")
        self.after(3600000, self.update_asteroid_data)
    def setup_disaster_tab(self):
        list_frame = customtkinter.CTkFrame(self.disaster_tab, fg_color="transparent"); list_frame.pack(fill="both", expand=True, padx=10, pady=10); customtkinter.CTkLabel(list_frame, text="Alertes de Catastrophes Mondiales (GDACS)", font=customtkinter.CTkFont(size=16, weight="bold")).pack(pady=10)
        self.disaster_log = ttk.Treeview(list_frame, columns=('Date', 'Type', 'Pays', 'Niveau', 'Link'), show='headings'); self.disaster_log.heading('Date', text='Date'); self.disaster_log.column('Date', width=150); self.disaster_log.heading('Type', text='Type de Catastrophe'); self.disaster_log.column('Type', width=150); self.disaster_log.heading('Pays', text='Pays/Région'); self.disaster_log.column('Pays', width=200); self.disaster_log.heading('Niveau', text='Niveau d\'Alerte'); self.disaster_log.column('Niveau', width=120, anchor='center'); self.disaster_log.column('Link', width=0, stretch=tkinter.NO); self.disaster_log.pack(fill="both", expand=True, padx=5, pady=5); self.disaster_log.tag_configure('Green', foreground='green'); self.disaster_log.tag_configure('Orange', foreground='orange', font=('Calibri', 10, 'bold')); self.disaster_log.tag_configure('Red', foreground='red', font=('Calibri', 12, 'bold')); self.disaster_log.bind("<Double-1>", self.on_disaster_double_click)
    def on_disaster_double_click(self, event):
        item_id = self.disaster_log.focus()
        if not item_id: return
        item = self.disaster_log.item(item_id)
        if item and 'values' in item and len(item['values']) > 0:
            link = item.get('values')[-1]
            if link and link.startswith('http'): webbrowser.open_new_tab(link)
    def update_disaster_data(self):
        disaster_update_interval = 1800000
        if self.is_playback_mode: self.after(disaster_update_interval, self.update_disaster_data); return
        try:
            print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Récupération des alertes GDACS..."); feed = feedparser.parse(GDACS_RSS_URL); self.disaster_log.delete(*self.disaster_log.get_children())
            for entry in feed.entries:
                alert_level = entry.get('gdacs_alertlevel', 'N/A'); tag = alert_level if alert_level in ['Green', 'Orange', 'Red'] else 'normal'; link = entry.get('link', '')
                self.disaster_log.insert('', 'end', values=(entry.get('published', 'N/A'), entry.get('gdacs_eventtype', 'N/A'), entry.get('gdacs_country', 'N/A'), alert_level, link), tags=(tag,))
        except Exception as e: print(f"Erreur API GDACS: {e}")
        self.after(disaster_update_interval, self.update_disaster_data)

if __name__ == "__main__":
    app = App()
    app.mainloop()