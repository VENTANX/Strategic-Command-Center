# ==============================================================================
# PROJECT: Command Center - Final, Complete and Stable Version
# Author: OUSSAMA ASLOUJ
# MODIFICATIONS: Complete integration of all major improvements.
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
import time
import json # For settings persistence
import csv # Added for export_log_to_csv

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
NASA_API_KEY = "ADN8Iy0BEt2cZr1FaBvEqG21cbt8a7BRC3mgJusu" # Your personal NASA API Key
SETTINGS_FILE = "command_center_settings.json"

# --- POLISH: API URLs centralized and verified ---
URLS = {
    "usgs_seismic_hour": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson",
    "usgs_seismic_day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson", # Used for initial seed
    "usgs_seismic_playback": "https://earthquake.usgs.gov/fdsnws/event/1/query", # Base URL for playback
    "nasa_cme": "https://api.nasa.gov/DONKI/CMEAnalysis?api_key=" + NASA_API_KEY,
    "nasa_flares": "https://api.nasa.gov/DONKI/FLR?api_key=" + NASA_API_KEY,
    # UPDATED: More reliable source for Flare Probabilities (NOAA GOES)
    "noaa_flare_prob": "https://services.swpc.noaa.gov/json/goes/primary/flare-fp-7-day.json", 
    # UPDATED: Confirmed stable for KP-Index (NOAA Planetary K-index)
    "noaa_kp_index": "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json", 
    # UPDATED: More specific endpoint for Solar Wind Plasma (speed, density)
    "noaa_solar_wind": "https://services.swpc.noaa.gov/products/solar-wind/plasma-1-minute.json", 
    "jpl_asteroids": "https://ssd-api.jpl.nasa.gov/cad.api"
}

SETTINGS_FILE = "command_center_settings.json"

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Centre de Commandement et d'Analyse Stratégique")
        self.geometry("1600x900")
        
        self.is_playback_mode = False
        self.is_demo_mode = False 
        self.processed_event_ids = set() # For seismic unique event tracking
        
        self.is_advanced_mode = tkinter.BooleanVar(value=False)
        self.seismic_time_series = deque(maxlen=50) 
        self.seismic_frequency = {} 
        
        # Solar Data for Graphs
        self.m_class_prob_history = deque(maxlen=24) # Stores (timestamp, probability) for last 24 hours
        self.x_class_prob_history = deque(maxlen=24)
        self.cme_daily_counts = {} # {date: count} for last 7 days
        self.solar_wind_speed_history = deque(maxlen=60) # Last hour of 1-min data
        self.solar_wind_density_history = deque(maxlen=60) # Last hour of 1-min data

        # Initialize values to avoid AttributeError before first update
        self.kp_index_val = 0 
        self.m_prob_val = 0
        self.x_prob_val = 0
        self.solar_wind_speed_val = 0
        self.solar_wind_density_val = 0

        # Map Overlay Toggles
        self.show_risk_zones = tkinter.BooleanVar(value=True)
        self.show_seismic_radii = tkinter.BooleanVar(value=True)

        # Alert Thresholds (default values)
        self.alert_seismic_mag = 6.0
        self.alert_seismic_depth = 50.0
        self.alert_kp_index = 5
        self.alert_cme_speed = 700 # km/s for 'moderate' storm potential
        self.alert_neo_distance_ld = 5.0 # Lunar Distances

        # Load settings
        self.load_settings()

        # Apply settings (theme, etc.)
        customtkinter.set_appearance_mode(self.settings.get("appearance_mode", "Dark"))
        customtkinter.set_default_color_theme(self.settings.get("color_theme", "blue"))

        try:
            self.seismic_model = joblib.load('anomaly_detector_model.joblib')
            self.seismic_scaler = joblib.load('data_scaler.joblib')
            self.tsunami_model = joblib.load('tsunami_predictor_model.joblib')
        except FileNotFoundError as e:
            messagebox.showerror("Erreur Critique", f"Fichier modèle introuvable : {e.filename}\nVeuillez lancer les scripts d'entraînement.")
            self.destroy(); return
        
        self.create_widgets()
        self.start_app()

    def load_settings(self):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                self.settings = json.load(f)
            # Apply loaded alert thresholds
            self.alert_seismic_mag = self.settings["alert_thresholds"].get("seismic_mag", 6.0)
            self.alert_seismic_depth = self.settings["alert_thresholds"].get("seismic_depth", 50.0)
            self.alert_kp_index = self.settings["alert_thresholds"].get("kp_index", 5)
            self.alert_cme_speed = self.settings["alert_thresholds"].get("cme_speed", 700)
            self.alert_neo_distance_ld = self.settings["alert_thresholds"].get("neo_distance_ld", 5.0)
            # Apply map overlay settings
            self.show_risk_zones.set(self.settings["map_overlays"].get("risk_zones", True))
            self.show_seismic_radii.set(self.settings["map_overlays"].get("seismic_radii", True))
        except (FileNotFoundError, json.JSONDecodeError):
            self.settings = {
                "appearance_mode": "Dark",
                "color_theme": "blue",
                "alert_thresholds": {
                    "seismic_mag": 6.0,
                    "seismic_depth": 50.0,
                    "kp_index": 5,
                    "cme_speed": 700,
                    "neo_distance_ld": 5.0
                },
                "map_overlays": {
                    "risk_zones": True,
                    "seismic_radii": True
                }
            }
        print("Settings loaded:", self.settings)

    def save_settings(self):
        self.settings["appearance_mode"] = customtkinter.get_appearance_mode()
        self.settings["color_theme"] = self.color_theme_optionemenu.get() 
        self.settings["alert_thresholds"]["seismic_mag"] = self.alert_seismic_mag
        self.settings["alert_thresholds"]["seismic_depth"] = self.alert_seismic_depth
        self.settings["alert_thresholds"]["kp_index"] = self.alert_kp_index
        self.settings["alert_thresholds"]["cme_speed"] = self.alert_cme_speed
        self.settings["alert_thresholds"]["neo_distance_ld"] = self.alert_neo_distance_ld
        self.settings["map_overlays"]["risk_zones"] = self.show_risk_zones.get()
        self.settings["map_overlays"]["seismic_radii"] = self.show_seismic_radii.get()

        with open(SETTINGS_FILE, 'w') as f:
            json.dump(self.settings, f, indent=4)
        print("Settings saved.")
        messagebox.showinfo("Paramètres Enregistrés", "Les paramètres ont été enregistrés avec succès.")

    def create_widgets(self):
        self.tab_view = customtkinter.CTkTabview(self, width=1580, height=880)
        self.tab_view.pack(pady=10, padx=10, fill="both", expand=True)

        self.seismic_tab = self.tab_view.add("Moniteur Sismique")
        self.solar_tab = self.tab_view.add("Activité Solaire")
        self.asteroid_tab = self.tab_view.add("Menaces Orbitales")
        self.disaster_tab = self.tab_view.add("Alertes Catastrophes")
        self.settings_tab = self.tab_view.add("Paramètres") # New Settings Tab

        self.setup_seismic_tab()
        self.setup_solar_tab()
        self.setup_asteroid_tab()
        self.setup_disaster_tab()
        self.setup_settings_tab()

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
        if not self.winfo_exists(): return

        self.status_label.configure(text="MODE: DIRECT", text_color="green")
        print("Système en mode surveillance directe.")
        
        def schedule_updates():
            if self.winfo_exists() and not self.is_demo_mode:
                self.update_seismic_data()
                self.update_solar_data()
                self.update_asteroid_data()
                self.update_disaster_data()
        
        self.after(100, schedule_updates)

    # ==================== MODULE SISMIQUE ====================
    def setup_seismic_tab(self):
        control_frame = customtkinter.CTkFrame(self.seismic_tab, height=80); control_frame.pack(side="top", fill="x", padx=10, pady=(10,5))
        customtkinter.CTkLabel(control_frame, text="Mode Relecture :", font=customtkinter.CTkFont(weight="bold")).pack(side="left", padx=(10,5))
        self.year_entry = customtkinter.CTkEntry(control_frame, placeholder_text="AAAA", width=60); self.year_entry.pack(side="left", padx=2)
        self.month_entry = customtkinter.CTkEntry(control_frame, placeholder_text="MM", width=40); self.month_entry.pack(side="left", padx=2)
        self.day_entry = customtkinter.CTkEntry(control_frame, placeholder_text="JJ", width=40); self.day_entry.pack(side="left", padx=2)
        
        # Date range for playback
        customtkinter.CTkLabel(control_frame, text="à :", font=customtkinter.CTkFont(weight="bold")).pack(side="left", padx=(10,5))
        self.year_end_entry = customtkinter.CTkEntry(control_frame, placeholder_text="AAAA", width=60); self.year_end_entry.pack(side="left", padx=2)
        self.month_end_entry = customtkinter.CTkEntry(control_frame, placeholder_text="MM", width=40); self.month_end_entry.pack(side="left", padx=2)
        self.day_end_entry = customtkinter.CTkEntry(control_frame, placeholder_text="JJ", width=40); self.day_end_entry.pack(side="left", padx=2)

        customtkinter.CTkButton(control_frame, text="Lancer Relecture", command=self.start_playback).pack(side="left", padx=10)
        customtkinter.CTkButton(control_frame, text="Retour au Direct", command=self.stop_playback).pack(side="left", padx=2)
        
        customtkinter.CTkButton(control_frame, text="Générer SITREP", command=self.generate_sitrep_window).pack(side="left", padx=20)
        
        # Map Overlay Checkboxes
        risk_zones_checkbox = customtkinter.CTkCheckBox(control_frame, text="Zones à Risque", variable=self.show_risk_zones, command=self.toggle_map_overlays)
        risk_zones_checkbox.pack(side="left", padx=10)
        seismic_radii_checkbox = customtkinter.CTkCheckBox(control_frame, text="Rayons Sismiques", variable=self.show_seismic_radii, command=self.toggle_map_overlays)
        seismic_radii_checkbox.pack(side="left", padx=10)


        self.status_label = customtkinter.CTkLabel(control_frame, text="INITIALISATION...", text_color="yellow", font=customtkinter.CTkFont(weight="bold")); self.status_label.pack(side="right", padx=20)
        advanced_switch = customtkinter.CTkSwitch(control_frame, text="Mode Avancé", variable=self.is_advanced_mode, command=self.toggle_advanced_mode); advanced_switch.pack(side="right", padx=20)
        main_frame = customtkinter.CTkFrame(self.seismic_tab, fg_color="transparent"); main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        self.data_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent"); self.data_frame.pack(side="left", fill="both", expand=True)
        map_frame = customtkinter.CTkFrame(self.data_frame); map_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        list_frame = customtkinter.CTkFrame(self.data_frame, width=420); list_frame.pack(side="right", fill="y", expand=False, padx=(5, 0))
        customtkinter.CTkLabel(list_frame, text="Journal des Détections", font=customtkinter.CTkFont(size=16, weight="bold")).pack(pady=10)
        self.map_widget = tkintermapview.TkinterMapView(map_frame, corner_radius=0); self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=19); self.map_widget.pack(fill="both", expand=True); self.draw_risk_zones()
        style = ttk.Style(); style.theme_use("default"); style.configure("Treeview", background="#2a2d2e", foreground="white", fieldbackground="#2a2d2e", borderwidth=0); style.map('Treeview', background=[('selected', '#22559b')]); style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat"); style.map("Treeview.Heading", background=[('active', '#3484F0')])
        self.seismic_log = ttk.Treeview(list_frame, columns=('Time', 'Mag', 'Depth', 'Status'), show='headings'); self.seismic_log.heading('Time', text='Heure'); self.seismic_log.column('Time', width=80, anchor='center'); self.seismic_log.heading('Mag', text='Mag.'); self.seismic_log.column('Mag', width=50, anchor='center'); self.seismic_log.heading('Depth', text='Prof.'); self.seismic_log.column('Depth', width=50, anchor='center'); self.seismic_log.heading('Status', text='Statut'); self.seismic_log.column('Status', width=180, anchor='w'); self.seismic_log.pack(fill="both", expand=True, padx=5, pady=5); self.seismic_log.tag_configure('normal', foreground='#00FF00'); self.seismic_log.tag_configure('low_anomaly', foreground='orange'); self.seismic_log.tag_configure('high_anomaly', foreground='red', font=('Calibri', 10, 'bold')); 
        self.seismic_log.tag_configure('critical_anomaly', foreground='magenta', font=('Calibri', 10, 'bold', 'underline')); 
        self.seismic_log.tag_configure('tsunami_risk', foreground='cyan', font=('Calibri', 10, 'bold')); self.seismic_log.tag_configure('slbm_anomaly', foreground='#FF69B4', font=('Calibri', 10, 'bold'))
        self.seismic_log.bind("<ButtonRelease-1>", self.on_seismic_log_click)

        # Export button for seismic log
        export_seismic_btn = customtkinter.CTkButton(list_frame, text="Exporter Journal", command=lambda: self.export_log_to_csv(self.seismic_log, "seismic_log.csv"))
        export_seismic_btn.pack(pady=5)

        self.graphs_frame = customtkinter.CTkFrame(main_frame, width=400)
        self.fig1, self.ax1 = plt.subplots(facecolor='#242424'); self.ax1.set_facecolor('#242424'); self.ax1.tick_params(axis='x', colors='white'); self.ax1.tick_params(axis='y', colors='white'); self.ax1.spines['bottom'].set_color('white'); self.ax1.spines['left'].set_color('white'); self.ax1.spines['top'].set_color('#242424'); self.ax1.spines['right'].set_color('#242424')
        self.canvas1 = FigureCanvasTkAgg(self.fig1, master=self.graphs_frame); self.canvas1.get_tk_widget().pack(fill="both", expand=True, pady=(10,5), padx=10)
        self.fig2, self.ax2 = plt.subplots(facecolor='#242424'); self.ax2.set_facecolor('#242424'); self.ax2.tick_params(axis='x', colors='white'); self.ax2.tick_params(axis='y', colors='white'); self.ax2.spines['bottom'].set_color('white'); self.ax2.spines['left'].set_color('white'); self.ax2.spines['top'].set_color('#242424'); self.ax2.spines['right'].set_color('#242424')
        self.canvas2 = FigureCanvasTkAgg(self.fig2, master=self.graphs_frame); self.canvas2.get_tk_widget().pack(fill="both", expand=True, pady=5, padx=10)
    
    def toggle_map_overlays(self):
        self.map_widget.delete_all_polygon()
        
        if self.show_risk_zones.get():
            self.draw_risk_zones()
        
        if self.show_seismic_radii.get():
            for marker in self.map_widget.canvas_marker_list:
                if hasattr(marker, 'data') and 'mag' in marker.data and 'lat' in marker.data and 'lon' in marker.data:
                    event_id = marker.data.get('id')
                    if event_id:
                        try:
                            radius_km = self.calculate_radius_from_magnitude(float(marker.data['mag']))
                            if radius_km > 0.5:
                                color = marker.marker_color_circle
                                self.map_widget.set_polygon(self.calculate_circle_points(marker.data['lat'], marker.data['lon'], radius_km), fill_color=color, outline_color=color, border_width=1, name=f"radius_{event_id}")
                        except ValueError:
                            print(f"Invalid magnitude for radius calculation: {marker.data['mag']}")


    def on_seismic_log_click(self, event):
        if not self.winfo_exists(): return
        item_id = self.seismic_log.focus()
        if not item_id: return

        item_tags = self.seismic_log.item(item_id, 'tags')
        event_data = next((tag for tag in item_tags if isinstance(tag, dict) and 'lat' in tag and 'lon' in tag), None)
        
        if event_data:
            lat = event_data['lat']
            lon = event_data['lon']
            mag = float(event_data['mag'])

            self.map_widget.set_position(lat, lon)
            
            if mag >= 7.0: self.map_widget.set_zoom(6)
            elif mag >= 6.0: self.map_widget.set_zoom(7)
            elif mag >= 5.0: self.map_widget.set_zoom(8)
            else: self.map_widget.set_zoom(9)

    def toggle_advanced_mode(self):
        if not self.winfo_exists(): return
        if self.is_advanced_mode.get():
            self.data_frame.pack_configure(side="left", fill="both", expand=True); self.graphs_frame.pack(side="right", fill="y", expand=False, padx=(5, 0))
            self.seismic_time_series.clear(); self.seismic_frequency.clear(); self.update_graphs()
        else: self.graphs_frame.pack_forget()
        threading.Thread(target=self.update_seismic_data, daemon=True).start()

    def update_graphs(self):
        if not self.winfo_exists(): return
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
        if not self.winfo_exists(): return
        if self.is_demo_mode: return

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
        if not self.winfo_exists(): return
        properties, geometry = event['properties'], event['geometry']
        mag = properties.get('mag')
        depth = geometry['coordinates'][2]
        lat = geometry['coordinates'][1]
        lon = geometry['coordinates'][0]

        if mag is None or depth is None or mag < 0: return

        mag_f = float(mag) if mag is not None else 0.0
        depth_f = float(depth) if depth is not None else 0.0

        if self.is_advanced_mode.get() and not is_playback:
            event_time = datetime.fromtimestamp(properties['time'] / 1000, tz=timezone.utc); self.seismic_time_series.append((event_time, mag_f))
            current_minute = event_time.replace(second=0, microsecond=0).timestamp(); self.seismic_frequency[current_minute] = self.seismic_frequency.get(current_minute, 0) + 1
        
        place_str = properties.get('place');
        if not place_str or place_str == "null": place_str = f"Coordonnées: {lat:.2f}, {lon:.2f}"
        
        features_anomaly = pd.DataFrame([[depth_f, mag_f]], columns=['Depth', 'Magnitude']); 
        features_anomaly_scaled = self.seismic_scaler.transform(features_anomaly)
        anomaly_score = self.seismic_model.decision_function(features_anomaly_scaled)[0]
        
        features_tsunami = pd.DataFrame([[depth_f, mag_f]], columns=['EQ_DEPTH', 'EQ_MAGNITUDE']); 
        tsunami_proba = self.tsunami_model.predict_proba(features_tsunami)[0][1]
        
        is_tsunami_risk = (tsunami_proba > 0.70 and mag_f > 7.5); 
        tsunami_risk_text = f" (Tsunami Prob. {tsunami_proba:.0%})" if is_tsunami_risk else ""
        
        zone = self.is_in_risk_zone(lat, lon); 
        status, color, tag, alert, yield_info = f"Normal{tsunami_risk_text}", "green", "normal", False, ""; 
        alert_title, alert_message = "", ""

        # --- Custom Alert Thresholds for Seismic ---
        if anomaly_score < -0.01 or mag_f >= self.alert_seismic_mag or depth_f <= self.alert_seismic_depth:
            estimated_yield = self.estimate_yield(mag_f); yield_info = f"\nPuissance Estimée: {estimated_yield}"
            if zone:
                if "SLBM" in zone: status, color, tag, alert_title, alert_message, alert = f"ANOMALIE ({zone})", "#FF69B4", "slbm_anomaly", "Alerte de Lancement Potentiel", f"Signature anormale détectée dans une zone d'essais SLBM connue: {zone} !", True
                else: status, color, tag, alert_title, alert_message, alert = f"CRITIQUE ({zone})", "magenta", "critical_anomaly", "ALERTE CRITIQUE GÉOPOLITIQUE", f"Anomalie forte détectée DANS une zone à haut risque: {zone} !", True
            elif anomaly_score < -0.1: status, color, tag, alert_title, alert_message, alert = "Anomalie Stratégique (Signature Artificielle)", "red", "high_anomaly", "Alerte de Sécurité", "Une signature sismique fortement anormale a été détectée, potentiellement artificielle.", True
            else: status, color, tag = "Anomalie Faible", "orange", "low_anomaly"
        elif is_tsunami_risk: status, color, tag, alert_title, alert_message, alert = f"Normal (RISQUE TSUNAMI)", "cyan", "tsunami_risk", "ALERTE TSUNAMI", "Un séisme avec un fort potentiel tsunamigène a été détecté.", True
        if is_tsunami_risk and status.startswith("Normal"): tag = "tsunami_risk"
        
        details = {
            'id': event.get('id', f"manual_event_{datetime.utcnow().timestamp()}"),
            'place': place_str, 
            'time': datetime.fromtimestamp(properties['time']/1000).strftime('%Y-%m-%d %H:%M:%S'), 
            'mag': f"{mag_f:.1f}", 
            'depth': f"{depth_f:.1f}", 
            'status': status, 
            'url': properties.get('url', ''), 
            'yield': yield_info.replace('\n', ''),
            'lat': lat, 
            'lon': lon  
        }
        
        marker = self.map_widget.set_marker(lat, lon, text=f"M{details['mag']}", marker_color_circle=color, command=self.on_marker_click_seismic); marker.data = details
        
        log_entry = (details['time'].split(' ')[1], details['mag'], details['depth'], status)
        self.seismic_log.insert('', 'end', values=log_entry, tags=(tag, details), iid=details['id']) 
        self.seismic_log.yview_moveto(1)
        
        try:
            radius_km = self.calculate_radius_from_magnitude(mag_f)
            if radius_km > 0.5 and self.show_seismic_radii.get(): # Apply toggle
                self.map_widget.set_polygon(self.calculate_circle_points(lat, lon, radius_km), fill_color=color, outline_color=color, border_width=1, name=f"radius_{details['id']}")
        except Exception as e: print(f"Erreur lors de la création du polygone de rayon : {e}")
        
        if status != "Normal": marker.final_color = color; self.pulse_marker(marker)
        if alert and not is_playback and not self.is_demo_mode and self.initial_seismic_load_complete: 
            messagebox.showwarning(alert_title, f"{alert_message}\n\nLieu: {details['place']}{yield_info}")
    
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
            item_tags = self.seismic_log.item(item_id, 'tags')
            status_tag = next((t for t in item_tags if isinstance(t, str) and t in ['high_anomaly', 'critical_anomaly', 'tsunami_risk', 'slbm_anomaly']), None)
            
            if status_tag:
                details = next((t for t in item_tags if isinstance(t, dict) and 'status' in t), None)
                if details:
                    seismic_alerts.append(f"    - ALERTE: {details['status']} (Mag {details['mag']}) détecté à {details['time'].split(' ')[1]} UTC. Lieu: {details['place']}")
        if seismic_alerts: report.extend(seismic_alerts)
        else: report.append("    - Aucune alerte de haut niveau active.")
        
        report.append(nl); report.append("2. DOMAINE SOLAIRE:")
        try:
            report.append(f"    - Probabilité Éruption (24h) -> Classe M: {self.m_prob_val}%, Classe X: {self.x_prob_val}%")
            report.append(f"    - {self.cme_summary_label.cget('text')}")
            report.append(f"    - {self.cme_eta_label.cget('text')}")
            report.append(f"    - Index KP Actuel: {self.kp_index_val}")
            report.append(f"    - Vitesse Vent Solaire: {self.solar_wind_speed_val:.1f} km/s")
            report.append(f"    - Densité Vent Solaire: {self.solar_wind_density_val:.1f} p/cc")
        except AttributeError: report.append("    - Données solaires non encore chargées.")
        
        report.append(nl); report.append("3. DOMAINE ORBITAL:"); high_risk_asteroids = []
        for item_id in self.asteroid_log.get_children():
            if 'high_risk' in self.asteroid_log.item(item_id, 'tags'): 
                values = self.asteroid_log.item(item_id, 'values'); 
                high_risk_asteroids.append(f"    - ALERTE RISQUE ÉLEVÉ: Objet '{values[1]}' en approche le {values[0]} (Distance: {values[3]} km, Diamètre: {values[2]} m).")
        if high_risk_asteroids: report.extend(high_risk_asteroids)
        else: report.append("    - Aucune menace orbitale à haut risque détectée.")
        
        report.append(nl); report.append("4. DOMAINE CATASTROPHES (GDACS):"); gdacs_alerts = []
        for item_id in self.disaster_log.get_children():
            if any(tag in self.disaster_log.item(item_id, 'tags') for tag in ['Red', 'Orange']):
                values = self.disaster_log.item(item_id, 'values'); gdacs_alerts.append(f"    - ALERTE {values[3].upper()}: {values[1]} en {values[2]}.")
        if gdacs_alerts: report.extend(gdacs_alerts)
        else: report.append("    - Aucune alerte GDACS orange ou rouge active.")
        report.append(nl); report.append("*"*30 + " FIN DU RAPPORT " + "*"*30); return "\n".join(report)
        
    def draw_risk_zones(self):
        self.map_widget.set_position(41.3, 129.1); self.map_widget.set_zoom(7)
        if self.show_risk_zones.get(): # Apply toggle
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
            if not self.winfo_exists(): return
            if steps > 0: marker.set_marker_color_circle("white" if marker.marker_color_circle != "white" else marker.final_color); self.after(150, lambda: self.pulse_marker(marker, steps - 1))
            else: marker.set_marker_color_circle(marker.final_color)
        except Exception: pass

    def start_playback(self):
        if not self.winfo_exists(): return
        if self.is_demo_mode: self.stop_demo_mode()
        
        try: 
            start_time = datetime(int(self.year_entry.get()), int(self.month_entry.get()), int(self.day_entry.get()))
            
            end_year_str = self.year_end_entry.get()
            end_month_str = self.month_end_entry.get()
            end_day_str = self.day_end_entry.get()

            if end_year_str and end_month_str and end_day_str:
                end_time = datetime(int(end_year_str), int(end_month_str), int(end_day_str)) + timedelta(days=1)
            else:
                end_time = start_time + timedelta(days=1) # Default to 1 day if end date not specified
            
        except ValueError: messagebox.showerror("Erreur de Date", "Veuillez entrer une date valide (AAAA, MM, JJ) pour les deux plages."); return
        
        if start_time >= end_time:
            messagebox.showerror("Erreur de Date", "La date de début doit être antérieure à la date de fin."); return

        self.is_playback_mode = True
        self.status_label.configure(text="MODE: RELECTURE", text_color="orange")
        self.seismic_log.delete(*self.seismic_log.get_children())
        self.map_widget.delete_all_marker()
        self.map_widget.delete_all_polygon()
        self.draw_risk_zones()
        self.processed_event_ids.clear() # Clear processed events for playback
        
        # Clear seismic graphs in playback mode
        self.seismic_time_series.clear()
        self.seismic_frequency.clear()
        if self.is_advanced_mode.get():
            self.update_graphs()

        try:
            url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={start_time.strftime('%Y-%m-%d')}&endtime={end_time.strftime('%Y-%m-%d')}&minmagnitude=3" # Limit magnitude for reasonable data size
            print(f"Fetching playback data from: {url}")
            response = requests.get(url, timeout=60); response.raise_for_status()
            events = sorted(response.json()['features'], key=lambda e: e['properties']['time'])
            
            if events:
                messagebox.showinfo("Relecture Chargée", f"{len(events)} événements trouvés pour la période sélectionnée. Démarrage de la relecture...")
                self.playback_next_event(events, 0)
            else:
                messagebox.showinfo("Info", "Aucun événement trouvé pour cette date."); self.stop_playback()
        except Exception as e: messagebox.showerror("Erreur API", f"Impossible de récupérer les données historiques: {e}"); self.stop_playback()

    def playback_next_event(self, events, index):
        if not self.winfo_exists(): return
        if index >= len(events) or not self.is_playback_mode: self.stop_playback(); return
        
        # Process and add a slight delay for visual effect
        self.process_single_seismic_event(events[index], is_playback=True)
        
        # Adjust zoom if needed during playback to show new events
        prop = events[index]['properties']
        geom = events[index]['geometry']['coordinates']
        lat, lon = geom[1], geom[0]
        mag = float(prop.get('mag', 0))
        
        self.map_widget.set_position(lat, lon)
        if mag >= 7.0: self.map_widget.set_zoom(6)
        elif mag >= 6.0: self.map_widget.set_zoom(7)
        elif mag >= 5.0: self.map_widget.set_zoom(8)
        else: self.map_widget.set_zoom(9)
        
        self.after(500, lambda: self.playback_next_event(events, index + 1)) # 0.5 second interval
        
    def stop_playback(self): 
        if not self.winfo_exists(): return
        self.is_playback_mode = False
        self.status_label.configure(text="SYNCHRONISANT...", text_color="yellow")
        self.map_widget.delete_all_marker()
        self.map_widget.delete_all_polygon()
        self.draw_risk_zones()
        self.seismic_log.delete(*self.seismic_log.get_children())
        self.processed_event_ids.clear() # Clear processed events on stop
        
        # Clear seismic graphs when stopping playback
        self.seismic_time_series.clear()
        self.seismic_frequency.clear()
        if self.is_advanced_mode.get():
            self.update_graphs()

        self.initial_seismic_load_complete = False
        threading.Thread(target=self.initial_data_seed, daemon=True).start()
    
    # ==================== DEMO MODE (Placeholder for potential future use) ====================
    def toggle_demo_mode(self):
        # Placeholder for demo mode toggle if My Lord wishes to re-implement
        messagebox.showinfo("Mode Démo", "Le mode démonstration n'est pas actif dans cette version complète.")

    def start_demo_mode(self):
        pass # Not active

    def _run_demo_playback(self):
        pass # Not active

    def stop_demo_mode(self):
        pass # Not active

    # ==================== MODULE SOLAIRE ====================
    def setup_solar_tab(self):
        main_frame = customtkinter.CTkFrame(self.solar_tab, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        top_panel = customtkinter.CTkFrame(main_frame)
        top_panel.pack(side="top", fill="x", pady=(0, 10))

        gauge_panel = customtkinter.CTkFrame(top_panel)
        gauge_panel.pack(side="left", padx=20, pady=10)
        customtkinter.CTkLabel(gauge_panel, text="Probabilité d'Éruption (24h)", font=customtkinter.CTkFont(size=16, weight="bold")).pack(pady=(0,10))
        
        prob_frame = customtkinter.CTkFrame(gauge_panel, fg_color="transparent")
        prob_frame.pack()
        self.m_class_gauge = tkinter.Canvas(prob_frame, width=150, height=150, bg="#2a2d2e", highlightthickness=0)
        self.m_class_gauge.pack(side="left", padx=10)
        self.x_class_gauge = tkinter.Canvas(prob_frame, width=150, height=150, bg="#2a2d2e", highlightthickness=0)
        self.x_class_gauge.pack(side="left", padx=10)
        
        self.kp_gauge = tkinter.Canvas(prob_frame, width=150, height=150, bg="#2a2d2e", highlightthickness=0)
        self.kp_gauge.pack(side="left", padx=10)

        # New: Solar Wind Gauges
        self.solar_wind_speed_gauge = tkinter.Canvas(prob_frame, width=150, height=150, bg="#2a2d2e", highlightthickness=0)
        self.solar_wind_speed_gauge.pack(side="left", padx=10)
        self.solar_wind_density_gauge = tkinter.Canvas(prob_frame, width=150, height=150, bg="#2a2d2e", highlightthickness=0)
        self.solar_wind_density_gauge.pack(side="left", padx=10)


        cme_summary_panel = customtkinter.CTkFrame(top_panel)
        cme_summary_panel.pack(side="left", expand=True, fill="both", padx=20, pady=10)
        customtkinter.CTkLabel(cme_summary_panel, text="État des Menaces CME", font=customtkinter.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=10)
        self.cme_summary_label = customtkinter.CTkLabel(cme_summary_panel, text="CMEs en transit vers la Terre : --", font=customtkinter.CTkFont(size=18), justify="left")
        self.cme_summary_label.pack(anchor="w", padx=10, pady=5)
        self.cme_eta_label = customtkinter.CTkLabel(cme_summary_panel, text="Prochain impact estimé : --", font=customtkinter.CTkFont(size=18), justify="left")
        self.cme_eta_label.pack(anchor="w", padx=10, pady=5)

        bottom_panel = customtkinter.CTkFrame(main_frame, fg_color="transparent")
        bottom_panel.pack(side="bottom", fill="both", expand=True)

        log_tab_view = customtkinter.CTkTabview(bottom_panel, width=700)
        log_tab_view.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        cme_tab = log_tab_view.add("Prévisions CME")
        flare_tab = log_tab_view.add("Journal des Éruptions (48h)")
        
        self.solar_cme_log = ttk.Treeview(cme_tab, columns=('StartTime', 'ArrivalTime', 'Speed', 'Risk'), show='headings')
        self.solar_cme_log.heading('StartTime', text='Heure de Départ (UTC)'); self.solar_cme_log.column('StartTime', width=180); 
        self.solar_cme_log.heading('ArrivalTime', text="Heure d'Arrivée Estimée (UTC)"); self.solar_cme_log.column('ArrivalTime', width=180); 
        self.solar_cme_log.heading('Speed', text='Vitesse (km/s)'); self.solar_cme_log.column('Speed', width=100, anchor='center'); 
        self.solar_cme_log.heading('Risk', text='Risque Tempête'); self.solar_cme_log.column('Risk', width=120, anchor='center'); 
        self.solar_cme_log.pack(fill="both", expand=True, padx=5, pady=5); 
        self.solar_cme_log.tag_configure('G3+', foreground='red', font=('Calibri', 11, 'bold')); 
        self.solar_cme_log.tag_configure('G1-G2', foreground='orange');
        self.solar_cme_log.bind("<Double-1>", self.on_cme_double_click)
        export_cme_btn = customtkinter.CTkButton(cme_tab, text="Exporter Journal CME", command=lambda: self.export_log_to_csv(self.solar_cme_log, "solar_cme_log.csv"))
        export_cme_btn.pack(pady=5)


        self.solar_flare_log = ttk.Treeview(flare_tab, columns=('Time', 'Class', 'Region', 'Geo-effective', 'Link'), show='headings'); 
        self.solar_flare_log.heading('Time', text='Heure Début (UTC)'); self.solar_flare_log.column('Time', width=150);
        self.solar_flare_log.heading('Class', text='Classe'); self.solar_flare_log.column('Class', width=80);
        self.solar_flare_log.heading('Region', text='Région Solaire'); self.solar_flare_log.column('Region', width=100);
        self.solar_flare_log.heading('Geo-effective', text='Menace Terre?'); self.solar_flare_log.column('Geo-effective', width=100, anchor='center');
        self.solar_flare_log.heading('Link', text='Link'); 
        self.solar_flare_log.column('Link', width=0, stretch=tkinter.NO); 
        self.solar_flare_log.pack(fill="both", expand=True, padx=5, pady=5); 
        self.solar_flare_log.tag_configure('geoeffective_x', foreground='red', font=('Calibri', 12, 'bold')); 
        self.solar_flare_log.tag_configure('geoeffective_m', foreground='orange', font=('Calibri', 11, 'bold'));
        self.solar_flare_log.bind("<Double-1>", self.on_flare_double_click)
        export_flare_btn = customtkinter.CTkButton(flare_tab, text="Exporter Journal Éruptions", command=lambda: self.export_log_to_csv(self.solar_flare_log, "solar_flare_log.csv"))
        export_flare_btn.pack(pady=5)
        
        solar_graphs_frame = customtkinter.CTkFrame(bottom_panel, width=800)
        solar_graphs_frame.pack(side="right", fill="both", expand=True)

        self.fig_solar_prob, self.ax_solar_prob = plt.subplots(facecolor='#242424', figsize=(7, 3)); self.ax_solar_prob.set_facecolor('#242424');
        self.ax_solar_prob.tick_params(axis='x', colors='white'); self.ax_solar_prob.tick_params(axis='y', colors='white');
        self.ax_solar_prob.spines['bottom'].set_color('white'); self.ax_solar_prob.spines['left'].set_color('white');
        self.ax_solar_prob.spines['top'].set_color('#242424'); self.ax_solar_prob.spines['right'].set_color('#242424');
        self.canvas_solar_prob = FigureCanvasTkAgg(self.fig_solar_prob, master=solar_graphs_frame); 
        self.canvas_solar_prob.get_tk_widget().pack(fill="both", expand=True, pady=(10,5), padx=10)

        self.fig_cme_count, self.ax_cme_count = plt.subplots(facecolor='#242424', figsize=(7, 3)); self.ax_cme_count.set_facecolor('#242424');
        self.ax_cme_count.tick_params(axis='x', colors='white'); self.ax_cme_count.tick_params(axis='y', colors='white');
        self.ax_cme_count.spines['bottom'].set_color('white'); self.ax_cme_count.spines['left'].set_color('white');
        self.ax_cme_count.spines['top'].set_color('#242424'); self.ax_cme_count.spines['right'].set_color('#242424');
        self.canvas_cme_count = FigureCanvasTkAgg(self.fig_cme_count, master=solar_graphs_frame); 
        self.canvas_cme_count.get_tk_widget().pack(fill="both", expand=True, pady=5, padx=10)

        # New: Solar Wind Speed/Density Trend Graph
        self.fig_solar_wind, self.ax_solar_wind = plt.subplots(facecolor='#242424', figsize=(7, 3)); self.ax_solar_wind.set_facecolor('#242424');
        self.ax_solar_wind.tick_params(axis='x', colors='white'); self.ax_solar_wind.tick_params(axis='y', colors='white');
        self.ax_solar_wind.spines['bottom'].set_color('white'); self.ax_solar_wind.spines['left'].set_color('white');
        self.ax_solar_wind.spines['top'].set_color('#242424'); self.ax_solar_wind.spines['right'].set_color('#242424');
        self.canvas_solar_wind = FigureCanvasTkAgg(self.fig_solar_wind, master=solar_graphs_frame); 
        self.canvas_solar_wind.get_tk_widget().pack(fill="both", expand=True, pady=5, padx=10)


        # Initialiser les jauges
        self.draw_gauge(self.m_class_gauge, 0, "Classe M", "orange")
        self.draw_gauge(self.x_class_gauge, 0, "Classe X", "red")
        self.draw_gauge(self.kp_gauge, 0, "KP-Index", "white", max_value=9)
        self.draw_gauge(self.solar_wind_speed_gauge, 0, "Vent Solaire (km/s)", "yellow", max_value=1000)
        self.draw_gauge(self.solar_wind_density_gauge, 0, "Densité (p/cc)", "lightgreen", max_value=50)

    def draw_gauge(self, canvas, value, name, color, max_value=100):
        canvas.delete("all")
        size = 150
        padding = 15
        
        canvas.create_arc(padding, padding, size-padding, size-padding, start=0, extent=359.9, style=tkinter.ARC, outline="#424242", width=12)
        
        if max_value > 0:
            extent = -(value / max_value * 359.9)
            if value > 0:
                canvas.create_arc(padding, padding, size-padding, size-padding, start=90, extent=extent, style=tkinter.ARC, outline=color, width=12)
        
        display_text = f"{int(value)}%" if "Classe" in name else f"{value:.1f}" if "km/s" in name or "p/cc" in name else f"{int(value)}"
        canvas.create_text(size/2, size/2, text=display_text, font=("Roboto", 24, "bold"), fill=color)
        canvas.create_text(size/2, size/2 + 30, text=name, font=("Roboto", 12), fill="white")

    def update_solar_data(self):
        if not self.winfo_exists(): return
        if self.is_playback_mode or self.is_demo_mode: self.after(1800000, self.update_solar_data); return
        
        threading.Thread(target=self.update_solar_flare_log_data, daemon=True).start()
        threading.Thread(target=self.update_solar_cme_data, daemon=True).start()
        threading.Thread(target=self.update_flare_probability_data, daemon=True).start()
        threading.Thread(target=self.update_kp_index, daemon=True).start()
        threading.Thread(target=self.update_solar_wind_data, daemon=True).start()

        self.after(1800000, self.update_solar_data)

    def update_solar_flare_log_data(self):
        try:
            end_date, start_date = datetime.utcnow(), datetime.utcnow() - timedelta(days=2)
            url=f"https://api.nasa.gov/DONKI/FLR?startDate={start_date.strftime('%Y-%m-%d')}&endDate={end_date.strftime('%Y-%m-%d')}&api_key={NASA_API_KEY}"
            flares_response = requests.get(url, timeout=10)
            flares_response.raise_for_status()
            flares = flares_response.json()
            if self.winfo_exists(): 
                self.after(0, self.populate_solar_flare_log, flares)
        except requests.exceptions.JSONDecodeError:
            print("Erreur API Solaire (FLR): Réponse non JSON ou vide.")
            if self.winfo_exists(): self.after(0, self.populate_solar_flare_log, [])
        except Exception as e: 
            print(f"Erreur API Solaire (FLR): {e}")
            if self.winfo_exists(): self.after(0, self.populate_solar_flare_log, [])

    def populate_solar_flare_log(self, flares):
        if not self.winfo_exists(): return
        self.solar_flare_log.delete(*self.solar_flare_log.get_children())
        for flare in reversed(flares):
            c_type = flare.get('classType', 'N/A')
            is_geo=self.is_flare_geoeffective(flare.get('sourceLocation')); geo_text="OUI" if is_geo else "Non"; tag='normal'
            if is_geo and (c_type.startswith('X') or c_type.startswith('M')): tag='geoeffective_x' if c_type.startswith('X') else 'geoeffective_m'
            
            flare_data = {
                'beginTime': flare.get('beginTime', 'N/A'),
                'classType': c_type,
                'sourceLocation': flare.get('sourceLocation', 'N/A'),
                'peakTime': flare.get('peakTime', 'N/A'),
                'endTime': flare.get('endTime', 'N/A'),
                'link': flare.get('link', ''),
                'activeRegionNum': flare.get('activeRegionNum', 'N/A')
            }
            unique_id = flare.get('flrID', f"flare_{datetime.utcnow().timestamp()}") 
            self.solar_flare_log.insert('', 'end', values=(flare.get('beginTime', 'N/A'), c_type, flare.get('sourceLocation', 'N/A'), geo_text, flare_data['link']), tags=(tag,), iid=unique_id)
            self.solar_flare_log.item(unique_id, tags=(tag, 'flare_data', flare_data)) 

    def on_flare_double_click(self, event):
        if not self.winfo_exists(): return
        item_id = self.solar_flare_log.focus()
        if not item_id: return
        
        item_tags = self.solar_flare_log.item(item_id, 'tags')
        flare_data = next((tag_item for tag_item in item_tags if isinstance(tag_item, dict) and 'classType' in tag_item), None)
        
        if flare_data:
            win = customtkinter.CTkToplevel(self)
            win.title("Détails de l'Éruption Solaire")
            win.geometry("550x300")

            text_content = (
                f"Début: {flare_data.get('beginTime', 'N/A').replace('T', ' ').replace('Z', ' UTC')}\n"
                f"Pic: {flare_data.get('peakTime', 'N/A').replace('T', ' ').replace('Z', ' UTC')}\n"
                f"Fin: {flare_data.get('endTime', 'N/A').replace('T', ' ').replace('Z', ' UTC')}\n"
                f"Classe: {flare_data.get('classType', 'N/A')}\n"
                f"Région Solaire: {flare_data.get('sourceLocation', 'N/A')}\n"
                f"Numéro Région Active: {flare_data.get('activeRegionNum', 'N/A')}\n"
                f"Géo-efficace pour la Terre: {'OUI' if self.is_flare_geoeffective(flare_data.get('sourceLocation')) else 'Non'}"
            )
            customtkinter.CTkLabel(win, text=text_content, justify=tkinter.LEFT, wraplength=500, font=("Roboto", 12)).pack(pady=10, padx=10, fill="both", expand=True)
            
            link = flare_data.get('link')
            if link and link.startswith('http'):
                customtkinter.CTkButton(win, text="Ouvrir sur le site de la NASA", command=lambda: webbrowser.open_new_tab(link)).pack(pady=10)

    def update_solar_cme_data(self):
        try:
            start_date=datetime.utcnow() - timedelta(days=7); end_date=datetime.utcnow()+timedelta(days=7)
            url=f"https://api.nasa.gov/DONKI/CMEAnalysis?startDate={start_date.strftime('%Y-%m-%d')}&endDate={end_date.strftime('%Y-%m-%d')}&mostAccurateOnly=true&api_key={NASA_API_KEY}"
            cme_response = requests.get(url, timeout=15)
            cme_response.raise_for_status()
            analyses = cme_response.json()
            if self.winfo_exists(): 
                self.after(0, self.populate_solar_cme_log, analyses)
        except requests.exceptions.JSONDecodeError:
            print("Erreur API Solaire (CME): Réponse non JSON ou vide.")
            if self.winfo_exists(): self.after(0, self.populate_solar_cme_log, [])
        except Exception as e: 
            print(f"Erreur API Solaire (CME): {e}")
            if self.winfo_exists(): self.after(0, self.populate_solar_cme_log, [])

    def populate_solar_cme_log(self, analyses):
        if not self.winfo_exists(): return
        self.solar_cme_log.delete(*self.solar_cme_log.get_children())
        cme_count = 0; next_eta = "Aucun"
        earth_bound_cmes = []
        
        self.cme_daily_counts = { (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d'): 0 for i in range(7) }

        for analysis in analyses:
            if analysis.get('isMostAccurate') and analysis.get('enlil') and analysis['enlil'].get('estimatedShockArrivalTime'):
                earth_bound_cmes.append(analysis)
                
                cme_time_str = analysis.get('time21_5', '').split('T')[0]
                if cme_time_str:
                    try:
                        cme_date = datetime.strptime(cme_time_str, '%Y-%m-%d').strftime('%Y-%m-%d')
                        if cme_date in self.cme_daily_counts:
                            self.cme_daily_counts[cme_date] += 1
                    except ValueError:
                        print(f"Could not parse CME date: {cme_time_str}")
        
        cme_count = len(earth_bound_cmes)
        if cme_count > 0:
            earth_bound_cmes.sort(key=lambda x: x['enlil']['estimatedShockArrivalTime'])
            next_eta = earth_bound_cmes[0]['enlil']['estimatedShockArrivalTime'].replace('T', ' ').replace('Z', ' UTC')
            for analysis in earth_bound_cmes:
                start_time = analysis.get('time21_5', 'N/A').replace('T', ' ').replace('Z', ''); 
                arrival_time = analysis['enlil'].get('estimatedShockArrivalTime', 'N/A').replace('T', ' ').replace('Z', ''); 
                speed = float(analysis['enlil'].get('speed', 0)); 
                
                risk_text, tag = self.get_geomagnetic_storm_risk(speed)
                
                cme_data = {
                    'startTime': analysis.get('time21_5', 'N/A'),
                    'arrivalTime': analysis['enlil'].get('estimatedShockArrivalTime', 'N/A'),
                    'speed': speed,
                    'isImpactor': analysis.get('isImpactor', False),
                    'kpForecast': analysis['enlil'].get('kp_forecast', 'N/A'), 
                    'url': analysis.get('link', '') 
                }
                
                unique_id = analysis.get('cmeAnalysisID', f"cme_{datetime.utcnow().timestamp()}")
                self.solar_cme_log.insert('', 'end', values=(start_time, arrival_time, f"{speed:.0f}", risk_text), tags=(tag,), iid=unique_id)
                self.solar_cme_log.item(unique_id, tags=(tag, 'cme_data', cme_data)) 
        
        self.cme_summary_label.configure(text=f"CMEs en transit vers la Terre : {cme_count}")
        self.cme_eta_label.configure(text=f"Prochain impact estimé : {next_eta}")
        self.update_solar_graphs()

    def on_cme_double_click(self, event):
        if not self.winfo_exists(): return
        item_id = self.solar_cme_log.focus()
        if not item_id: return
        
        item_tags = self.solar_cme_log.item(item_id, 'tags')
        cme_data = next((tag_item for tag_item in item_tags if isinstance(tag_item, dict) and 'speed' in tag_item), None)
        
        if cme_data:
            win = customtkinter.CTkToplevel(self)
            win.title("Détails du CME")
            win.geometry("550x300")

            text_content = (
                f"Départ du Soleil: {cme_data.get('startTime', 'N/A').replace('T', ' ').replace('Z', ' UTC')}\n"
                f"Arrivée estimée (Terre): {cme_data.get('arrivalTime', 'N/A').replace('T', ' ').replace('Z', ' UTC')}\n"
                f"Vitesse Initiale: {cme_data.get('speed', 'N/A'):.0f} km/s\n"
                f"Potentiel Impactor: {'Oui' if cme_data.get('isImpactor', False) else 'Non'}\n"
                f"Prévision KP-index Max: {cme_data.get('kpForecast', 'N/A')}\n"
                f"Risque de Tempête Géomagnétique: {self.get_geomagnetic_storm_risk(cme_data.get('speed', 0))[0]}"
            )
            customtkinter.CTkLabel(win, text=text_content, justify=tkinter.LEFT, wraplength=500, font=("Roboto", 12)).pack(pady=10, padx=10, fill="both", expand=True)
            
            link = cme_data.get('url')
            if link and link.startswith('http'):
                customtkinter.CTkButton(win, text="Ouvrir l'Analyse sur le site de la NASA", command=lambda: webbrowser.open_new_tab(link)).pack(pady=10)

    def get_geomagnetic_storm_risk(self, speed):
        # Simplified G-scale approximation based on speed
        # Check against custom alert threshold
        if speed >= 1500: return "G5 (Extrême)", "G3+" 
        elif speed >= 1000: return "G4 (Sévère)", "G3+"
        elif speed >= 800 or speed >= self.alert_cme_speed: # Use custom threshold for G3+
            return "G3 (Fort)", "G3+"
        elif speed >= 600: return "G2 (Modéré)", "G1-G2"
        elif speed >= 500: return "G1 (Faible)", "G1-G2"
        else: return "Nul", "normal"

    def update_flare_probability_data(self):
        if self.is_demo_mode: return
        try:
            url = NASA_SFP_URL
            swf_response = requests.get(url, timeout=10)
            swf_response.raise_for_status()
            preds_data = swf_response.json()
            
            m_prob, x_prob = 0, 0
            if preds_data and isinstance(preds_data, list):
                latest_forecast = preds_data[-1] 
                
                message = latest_forecast.get('message', '').lower()
                
                m_match = re.search(r'm-flare probability: (\d+)%', message)
                x_match = re.search(r'x-flare probability: (\d+)%', message)

                if m_match: m_prob = int(m_match.group(1))
                if x_match: x_prob = int(x_match.group(1))

            current_time = datetime.utcnow()
            self.m_class_prob_history.append((current_time, m_prob))
            self.x_class_prob_history.append((current_time, x_prob))

            if self.winfo_exists(): 
                self.after(0, self.populate_flare_probability, m_prob, x_prob)
                self.update_solar_graphs() 

        except requests.exceptions.JSONDecodeError:
            print("Erreur API Solaire (SFP/SWF): Réponse non JSON ou vide. Tentative de récupération ultérieure.")
            m_prob, x_prob = 0, 0
            self.m_class_prob_history.clear()
            self.x_class_prob_history.clear()
            if self.winfo_exists(): self.after(0, self.populate_flare_probability, m_prob, x_prob)
        except Exception as e: 
            print(f"Erreur API Solaire (SFP/SWF): {e}. Tentative de récupération ultérieure.")
            m_prob, x_prob = 0, 0
            self.m_class_prob_history.clear()
            self.x_class_prob_history.clear()
            if self.winfo_exists(): self.after(0, self.populate_flare_probability, m_prob, x_prob)
    
    def populate_flare_probability(self, m_prob, x_prob):
        if not self.winfo_exists(): return
        self.m_prob_val = m_prob
        self.x_prob_val = x_prob
        
        self.draw_gauge(self.m_class_gauge, m_prob, "Classe M", "orange")
        self.draw_gauge(self.x_class_gauge, x_prob, "Classe X", "red")

    def update_kp_index(self):
        if self.is_demo_mode: return
        try:
            response = requests.get(NOAA_KP_INDEX_URL, timeout=5)
            response.raise_for_status()
            kp_data = response.json()

            latest_kp = 0
            if kp_data and isinstance(kp_data, list):
                # The NOAA planetary-k-index.json format is [time_tag, kp_value].
                # We need to ensure we get the latest valid entry.
                valid_kp_entries = [entry for entry in kp_data if len(entry) > 1 and entry[1] is not None]

                if valid_kp_entries:
                    # The API data might not always be perfectly sorted, sort by timestamp (index 0)
                    # The timestamp is typically in ISO format, sorting strings works for ISO dates
                    sorted_valid_kp_entries = sorted(valid_kp_entries, key=lambda x: x[0])
                    latest_kp_entry = sorted_valid_kp_entries[-1]
                    try:
                        latest_kp = int(round(float(latest_kp_entry[1]))) # Kp is the second element (index 1)
                    except ValueError:
                        print(f"Could not parse Kp value from {latest_kp_entry[1]}")
                        latest_kp = 0 # Default to 0 on parse error

            self.kp_index_val = latest_kp
            if self.winfo_exists():
                self.after(0, lambda: self.draw_gauge(self.kp_gauge, self.kp_index_val, "KP-Index", "white", max_value=9))
                if latest_kp >= self.alert_kp_index: # Custom alert threshold for Kp-index
                    messagebox.showwarning("ALERTE KP-INDEX", f"KP-Index actuel élevé: {latest_kp} (seuil: {self.alert_kp_index}) - Risque de tempête géomagnétique!")

        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la récupération du KP-Index: {e}")
            self.kp_index_val = 0
            if self.winfo_exists(): self.after(0, lambda: self.draw_gauge(self.kp_gauge, self.kp_index_val, "KP-Index", "white", max_value=9))
        except requests.exceptions.JSONDecodeError:
            print("Erreur KP-Index: Réponse NOAA non JSON ou vide.")
            self.kp_index_val = 0
            if self.winfo_exists(): self.after(0, lambda: self.draw_gauge(self.kp_gauge, self.kp_index_val, "KP-Index", "white", max_value=9))
        except Exception as e:
            print(f"Erreur inattendue lors de l'analyse du KP-Index: {e}")
            self.kp_index_val = 0
            if self.winfo_exists(): self.after(0, lambda: self.draw_gauge(self.kp_gauge, self.kp_index_val, "KP-Index", "white", max_value=9))
        
        self.after(300000, self.update_kp_index)

    def update_solar_wind_data(self):
        if self.is_demo_mode: return
        try:
            response = requests.get(NOAA_SOLAR_WIND_URL, timeout=5)
            response.raise_for_status()
            solar_wind_data = response.json()

            current_speed = 0.0
            current_density = 0.0

            if solar_wind_data and isinstance(solar_wind_data, list):
                valid_entries = [entry for entry in solar_wind_data if entry.get('speed') is not None and entry.get('density') is not None]
                if valid_entries:
                    latest_entry = valid_entries[-1]
                    current_speed = float(latest_entry.get('speed', 0.0))
                    current_density = float(latest_entry.get('density', 0.0))
            
            current_time = datetime.utcnow()
            self.solar_wind_speed_history.append((current_time, current_speed))
            self.solar_wind_density_history.append((current_time, current_density))

            self.solar_wind_speed_val = current_speed
            self.solar_wind_density_val = current_density

            if self.winfo_exists():
                self.after(0, lambda: self.draw_gauge(self.solar_wind_speed_gauge, self.solar_wind_speed_val, "Vent Solaire (km/s)", "yellow", max_value=1000))
                self.after(0, lambda: self.draw_gauge(self.solar_wind_density_gauge, self.solar_wind_density_val, "Densité (p/cc)", "lightgreen", max_value=50))
                self.update_solar_graphs()

        except requests.exceptions.RequestException as e:
            print(f"Erreur lors de la récupération des données de vent solaire: {e}")
            self.solar_wind_speed_val = 0.0
            self.solar_wind_density_val = 0.0
            if self.winfo_exists():
                self.after(0, lambda: self.draw_gauge(self.solar_wind_speed_gauge, self.solar_wind_speed_val, "Vent Solaire (km/s)", "yellow", max_value=1000))
                self.after(0, lambda: self.draw_gauge(self.solar_wind_density_gauge, self.solar_wind_density_val, "Densité (p/cc)", "lightgreen", max_value=50))
        except requests.exceptions.JSONDecodeError:
            print("Erreur Vent Solaire: Réponse NOAA non JSON ou vide.")
            self.solar_wind_speed_val = 0.0
            self.solar_wind_density_val = 0.0
            if self.winfo_exists():
                self.after(0, lambda: self.draw_gauge(self.solar_wind_speed_gauge, self.solar_wind_speed_val, "Vent Solaire (km/s)", "yellow", max_value=1000))
                self.after(0, lambda: self.draw_gauge(self.solar_wind_density_gauge, self.solar_wind_density_val, "Densité (p/cc)", "lightgreen", max_value=50))
        except Exception as e:
            print(f"Erreur inattendue lors de l'analyse des données de vent solaire: {e}")
            self.solar_wind_speed_val = 0.0
            self.solar_wind_density_val = 0.0
            if self.winfo_exists():
                self.after(0, lambda: self.draw_gauge(self.solar_wind_speed_gauge, self.solar_wind_speed_val, "Vent Solaire (km/s)", "yellow", max_value=1000))
                self.after(0, lambda: self.draw_gauge(self.solar_wind_density_gauge, self.solar_wind_density_val, "Densité (p/cc)", "lightgreen", max_value=50))
        
        self.after(60000, self.update_solar_wind_data)

    def update_solar_graphs(self):
        if not self.winfo_exists(): return
        
        self.ax_solar_prob.cla()
        if self.m_class_prob_history or self.x_class_prob_history:
            if self.m_class_prob_history:
                sorted_m_history = sorted(self.m_class_prob_history, key=lambda x: x[0])
                m_times, m_probs = zip(*sorted_m_history)
                self.ax_solar_prob.plot(m_times, m_probs, label='Classe M', color='orange', marker='o', markersize=3)
            if self.x_class_prob_history:
                sorted_x_history = sorted(self.x_class_prob_history, key=lambda x: x[0])
                x_times, x_probs = zip(*sorted_x_history)
                self.ax_solar_prob.plot(x_times, x_probs, label='Classe X', color='red', marker='o', markersize=3)
            self.ax_solar_prob.legend(loc='upper left', frameon=False, labelcolor='white')

        self.ax_solar_prob.set_title("Probabilité d'Éruption (24h)", color='white', fontsize=10)
        self.ax_solar_prob.set_ylabel("Probabilité (%)", color='white', fontsize=8)
        self.ax_solar_prob.set_ylim(0, 100)
        self.fig_solar_prob.autofmt_xdate()
        self.fig_solar_prob.tight_layout(pad=2.0)
        self.canvas_solar_prob.draw()

        self.ax_cme_count.cla()
        if self.cme_daily_counts:
            sorted_dates_objects = sorted([datetime.strptime(d, '%Y-%m-%d') for d in self.cme_daily_counts.keys()])
            sorted_dates_str = [d.strftime('%Y-%m-%d') for d in sorted_dates_objects]
            counts = [self.cme_daily_counts[date_str] for date_str in sorted_dates_str]
            self.ax_cme_count.bar(sorted_dates_str, counts, color='cyan')

        self.ax_cme_count.set_title("Nb. CMEs (7 derniers jours)", color='white', fontsize=10)
        self.ax_cme_count.set_ylabel("Nb. CMEs", color='white', fontsize=8)
        plt.setp(self.ax_cme_count.get_xticklabels(), rotation=45, ha="right")
        self.fig_cme_count.tight_layout(pad=2.0)
        self.canvas_cme_count.draw()

        self.ax_solar_wind.cla()
        if self.solar_wind_speed_history or self.solar_wind_density_history:
            if self.solar_wind_speed_history:
                sorted_speed_history = sorted(self.solar_wind_speed_history, key=lambda x: x[0])
                speed_times, speeds = zip(*sorted_speed_history)
                self.ax_solar_wind.plot(speed_times, speeds, label='Vitesse (km/s)', color='yellow', marker='.', markersize=2)
            if self.solar_wind_density_history:
                sorted_density_history = sorted(self.solar_wind_density_history, key=lambda x: x[0])
                density_times, densities = zip(*sorted_density_history)
                self.ax_solar_wind.plot(density_times, densities, label='Densité (p/cc)', color='lightgreen', marker='.', markersize=2)
            self.ax_solar_wind.legend(loc='upper left', frameon=False, labelcolor='white')
            
        self.ax_solar_wind.set_title("Vent Solaire (60 min)", color='white', fontsize=10)
        self.ax_solar_wind.set_ylabel("Valeur", color='white', fontsize=8)
        self.fig_solar_wind.autofmt_xdate()
        self.fig_solar_wind.tight_layout(pad=2.0)
        self.canvas_solar_wind.draw()

    def is_flare_geoeffective(self, location_string):
        if not location_string: return False
        match = re.search(r'[EW](\d+)', location_string.upper())
        return match and int(match.group(1)) < 60

    # ==================== MODULE ORBITAL ====================
    def setup_asteroid_tab(self):
        summary_frame = customtkinter.CTkFrame(self.asteroid_tab, fg_color="transparent"); summary_frame.pack(fill="x", padx=10, pady=10); 
        self.asteroid_summary_label1 = customtkinter.CTkLabel(summary_frame, text="Approche la plus Proche: --", font=customtkinter.CTkFont(size=15, weight="bold")); self.asteroid_summary_label1.pack(side="left", padx=20); 
        self.asteroid_summary_label2 = customtkinter.CTkLabel(summary_frame, text="Objet le plus Large: --", font=customtkinter.CTkFont(size=15, weight="bold")); self.asteroid_summary_label2.pack(side="left", padx=20); 
        self.asteroid_summary_label3 = customtkinter.CTkLabel(summary_frame, text="Alertes de Risque Élevé: --", font=customtkinter.CTkFont(size=15, weight="bold")); self.asteroid_summary_label3.pack(side="left", padx=20)
        
        list_frame = customtkinter.CTkFrame(self.asteroid_tab, fg_color="transparent"); list_frame.pack(fill="both", expand=True, padx=10, pady=0); 
        self.asteroid_log=ttk.Treeview(list_frame, columns=('Date', 'Name', 'Diameter', 'Distance', 'Risk'), show='headings'); 
        self.asteroid_log.heading('Date', text='Date Passage'); self.asteroid_log.column('Date', width=180); 
        self.asteroid_log.heading('Name', text='Nom Objet'); self.asteroid_log.column('Name', width=180); 
        self.asteroid_log.heading('Diameter', text='Diamètre Est. (m)'); self.asteroid_log.column('Diameter', width=150, anchor='center'); 
        self.asteroid_log.heading('Distance', text='Distance Passage (km)'); self.asteroid_log.column('Distance', width=180, anchor='center'); 
        self.asteroid_log.heading('Risk', text='Score Risque'); self.asteroid_log.column('Risk', width=100, anchor='center'); 
        self.asteroid_log.pack(fill="both", expand=True, padx=5, pady=5); 
        self.asteroid_log.tag_configure('low_risk', foreground='yellow'); 
        self.asteroid_log.tag_configure('medium_risk', foreground='orange'); 
        self.asteroid_log.tag_configure('high_risk', foreground='red', font=('Calibri', 10, 'bold'))
        self.asteroid_log.bind("<Double-1>", self.on_asteroid_double_click) # Bind double click for details/map
        
        export_asteroid_btn = customtkinter.CTkButton(list_frame, text="Exporter Journal Orbites", command=lambda: self.export_log_to_csv(self.asteroid_log, "asteroid_log.csv"))
        export_asteroid_btn.pack(pady=5)

        neo_map_frame = customtkinter.CTkFrame(self.asteroid_tab, fg_color="transparent", height=300)
        neo_map_frame.pack(fill="x", padx=10, pady=10)
        customtkinter.CTkLabel(neo_map_frame, text="Prochaine Approche Proche (Planétaire)", font=customtkinter.CTkFont(size=16, weight="bold")).pack(pady=5)
        self.neo_map_label = customtkinter.CTkLabel(neo_map_frame, text="Aucun objet à l'approche dangereuse détecté.", font=customtkinter.CTkFont(size=14))
        self.neo_map_label.pack(pady=5)

    def on_asteroid_double_click(self, event):
        if not self.winfo_exists(): return
        item_id = self.asteroid_log.focus()
        if not item_id: return
        
        values = self.asteroid_log.item(item_id, 'values')
        if not values: return

        name = values[1] if len(values) > 1 else "N/A"
        date_pass = values[0] if len(values) > 0 else "N/A"
        diameter = values[2] if len(values) > 2 else "N/A"
        distance_km_str = values[3] if len(values) > 3 else "N/A"
        risk_score = values[4] if len(values) > 4 else "N/A"

        win = customtkinter.CTkToplevel(self)
        win.title(f"Détails de l'Objet Orbital: {name}")
        win.geometry("500x250")

        text_content = (
            f"Nom de l'Objet: {name}\n"
            f"Date de Passage: {date_pass}\n"
            f"Diamètre Estimé: {diameter} m\n"
            f"Distance de Passage: {distance_km_str} km\n"
            f"Score de Risque: {risk_score}\n\n"
            "Pour plus de détails, recherchez sur le site du JPL Small-Body Database."
        )
        customtkinter.CTkLabel(win, text=text_content, justify=tkinter.LEFT, wraplength=480, font=("Roboto", 12)).pack(pady=10, padx=10, fill="both", expand=True)
        
        search_url = f"https://ssd.jpl.nasa.gov/tools/sbdb_query.html#/?sstr={name}"
        customtkinter.CTkButton(win, text=f"Rechercher '{name}' sur JPL SBDB", command=lambda: webbrowser.open_new_tab(search_url)).pack(pady=10)

        self.tab_view.set("Moniteur Sismique")
        self.map_widget.set_position(0, 0) # Center on Earth
        self.map_widget.set_zoom(1) # Global view

        if "Élevé" in risk_score or "Modéré" in risk_score:
            self.neo_map_label.configure(text=f"ALERTE: Approche proche de {name} ({distance_km_str} km) - RISQUE {risk_score.upper()}")


    def calculate_risk_score(self, d_m, dist_km):
        score=0
        ld = dist_km / 384400 # Convert km to Lunar Distances
        if d_m > 25 and ld < 20: score+=1
        if d_m > 140: score+=1
        if ld < 5: score+=1
        if ld < 1: score+=2
        
        if ld <= self.alert_neo_distance_ld: # Custom NEO distance threshold
            score += 1

        if score >= 4: return "Élevé", "high_risk"
        if score >= 2: return "Modéré", "medium_risk"
        if score > 0: return "Faible", "low_risk"
        return "Nul", "normal"

    def update_asteroid_data(self):
        if not self.winfo_exists(): return
        if self.is_playback_mode or self.is_demo_mode: self.after(3600000, self.update_asteroid_data); return
        try:
            url=f"https://ssd-api.jpl.nasa.gov/cad.api?dist-max=20LD&date-max=60&sort=dist&api_key={NASA_API_KEY}" 
            asteroids=requests.get(url, timeout=15).json(); 
            self.asteroid_log.delete(*self.asteroid_log.get_children())
            
            close_name, large_name = "--", "--"; 
            close_dist, large_diam, high_risk_count = float('inf'), 0, 0
            
            self.neo_map_label.configure(text="Aucun objet à l'approche dangereuse détecté.")

            if int(asteroids.get('count', 0)) > 0:
                AU_TO_KM = 149597870.7
                
                for data in asteroids['data']:
                    data_map={f: v for f, v in zip(asteroids['fields'], data)}; 
                    
                    dist_au = float(data_map.get('dist', 0))
                    dist_km = dist_au * AU_TO_KM 
                    
                    h_mag = float(data_map.get('h', 25)); 
                    d_m = (1329000 / (10**(0.2 * h_mag))) if h_mag > 0 else 0 
                    
                    if dist_km < close_dist: 
                        close_dist, close_name = dist_km, data_map.get('des')
                    if d_m > large_diam: 
                        large_diam, large_name = d_m, data_map.get('des')
                    
                    risk_text, risk_tag = self.calculate_risk_score(d_m, dist_km)
                    if risk_tag == "high_risk": 
                        high_risk_count += 1
                        messagebox.showwarning("ALERTE ORBITALE", f"OBJET À RISQUE ÉLEVÉ DÉTECTÉ: {data_map.get('des')}\nApproche le {data_map.get('cd')} à {dist_km:,.0f} km.\nDiamètre estimé: {d_m:.0f} m.")
                        self.neo_map_label.configure(text=f"ALERTE: Approche proche de {data_map.get('des')} ({dist_km:,.0f} km) - RISQUE {risk_text.upper()}")

                    self.asteroid_log.insert('', 'end', values=(data_map.get('cd'), data_map.get('des'), f"{d_m:.0f}", f"{dist_km:,.0f}", risk_text), tags=(risk_tag,))
            
            self.asteroid_summary_label1.configure(text=f"Approche la plus Proche: {close_name} ({close_dist:,.0f} km)")
            self.asteroid_summary_label2.configure(text=f"Objet le plus Large: {large_name} (~{large_diam:.0f} m)")
            self.asteroid_summary_label3.configure(text=f"Alertes de Risque Élevé: {high_risk_count}")
        except Exception as e: print(f"Erreur API Astéroïdes: {e}")
        self.after(3600000, self.update_asteroid_data)

    # ==================== MODULE CATASTROPHES ====================
    def setup_disaster_tab(self):
        list_frame = customtkinter.CTkFrame(self.disaster_tab, fg_color="transparent"); list_frame.pack(fill="both", expand=True, padx=10, pady=10); 
        customtkinter.CTkLabel(list_frame, text="Alertes de Catastrophes Mondiales (GDACS)", font=customtkinter.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        self.disaster_log = ttk.Treeview(list_frame, columns=('Date', 'Type', 'Pays', 'Niveau', 'Link', 'Lat', 'Lon'), show='headings'); 
        self.disaster_log.heading('Date', text='Date'); self.disaster_log.column('Date', width=150); 
        self.disaster_log.heading('Type', text='Type de Catastrophe'); self.disaster_log.column('Type', width=150); 
        self.disaster_log.heading('Pays', text='Pays/Région'); self.disaster_log.column('Pays', width=200); 
        self.disaster_log.heading('Niveau', text='Niveau d\'Alerte'); self.disaster_log.column('Niveau', width=120, anchor='center'); 
        self.disaster_log.column('Link', width=0, stretch=tkinter.NO);
        self.disaster_log.column('Lat', width=0, stretch=tkinter.NO);
        self.disaster_log.column('Lon', width=0, stretch=tkinter.NO);
        self.disaster_log.pack(fill="both", expand=True, padx=5, pady=5); 
        self.disaster_log.tag_configure('Green', foreground='green'); 
        self.disaster_log.tag_configure('Orange', foreground='orange', font=('Calibri', 10, 'bold')); 
        self.disaster_log.tag_configure('Red', foreground='red', font=('Calibri', 12, 'bold')); 
        self.disaster_log.bind("<Double-1>", self.on_disaster_double_click)

        export_disaster_btn = customtkinter.CTkButton(list_frame, text="Exporter Journal Catastrophes", command=lambda: self.export_log_to_csv(self.disaster_log, "disaster_log.csv"))
        export_disaster_btn.pack(pady=5)

    def on_disaster_double_click(self, event):
        if not self.winfo_exists(): return
        item_id = self.disaster_log.focus()
        if not item_id: return
        item = self.disaster_log.item(item_id)
        if item and 'values' in item and len(item['values']) > 0:
            link = item.get('values')[4]
            lat = item.get('values')[5] if len(item.get('values')) > 5 else None
            lon = item.get('values')[6] if len(item.get('values')) > 6 else None

            if link and link.startswith('http'): 
                webbrowser.open_new_tab(link)
            
            if lat is not None and lon is not None:
                try:
                    self.tab_view.set("Moniteur Sismique") 
                    self.map_widget.set_position(float(lat), float(lon))
                    self.map_widget.set_zoom(7) 
                except ValueError:
                    print(f"Invalid lat/lon for disaster event: {lat}, {lon}")


    def update_disaster_data(self):
        if not self.winfo_exists(): return
        if self.is_playback_mode or self.is_demo_mode: self.after(1800000, self.update_disaster_data); return
        disaster_update_interval = 1800000
        try:
            print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Récupération des alertes GDACS..."); feed = feedparser.parse(GDACS_RSS_URL); self.disaster_log.delete(*self.disaster_log.get_children())
            for entry in feed.entries:
                alert_level = entry.get('gdacs_alertlevel', 'N/A'); tag = alert_level if alert_level in ['Green', 'Orange', 'Red'] else 'normal'; 
                link = entry.get('link', '')
                
                lat, lon = None, None
                if hasattr(entry, 'georss_point') and entry.georss_point:
                    try:
                        coords = entry.georss_point.split(' ')
                        lat, lon = float(coords[0]), float(coords[1])
                    except ValueError: pass
                elif hasattr(entry, 'gdacs_point') and entry.gdacs_point:
                    try:
                        coords = entry.gdacs_point.split(' ')
                        lat, lon = float(coords[0]), float(coords[1])
                    except ValueError: pass
                
                self.disaster_log.insert('', 'end', values=(entry.get('published', 'N/A'), entry.get('gdacs_eventtype', 'N/A'), entry.get('gdacs_country', 'N/A'), alert_level, link, lat, lon), tags=(tag,))
                
                if alert_level in ['Orange', 'Red']:
                    messagebox.showwarning("ALERTE CATASTROPHE", f"GDACS: Alerte {alert_level} pour {entry.get('gdacs_eventtype')} en {entry.get('gdacs_country')}!")

        except Exception as e: print(f"Erreur API GDACS: {e}")
        self.after(disaster_update_interval, self.update_disaster_data)

    # ==================== MODULE PARAMETRES ====================
    def setup_settings_tab(self):
        settings_frame = customtkinter.CTkFrame(self.settings_tab, fg_color="transparent")
        settings_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Appearance Mode
        customtkinter.CTkLabel(settings_frame, text="Mode d'Apparence :", font=customtkinter.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.appearance_mode_optionemenu = customtkinter.CTkOptionMenu(settings_frame, values=["Light", "Dark", "System"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.set(customtkinter.get_appearance_mode())
        self.appearance_mode_optionemenu.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Color Theme
        customtkinter.CTkLabel(settings_frame, text="Thème de Couleur :", font=customtkinter.CTkFont(weight="bold")).grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.color_theme_optionemenu = customtkinter.CTkOptionMenu(settings_frame, values=["blue", "green", "dark-blue"],
                                                                     command=self.change_color_theme_event)
        self.color_theme_optionemenu.set(self.settings.get("color_theme", "blue")) # Corrected: use value from settings
        self.color_theme_optionemenu.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # Alert Thresholds Section
        alert_thresholds_frame = customtkinter.CTkFrame(settings_frame, fg_color="transparent")
        alert_thresholds_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=20, sticky="nsew")
        customtkinter.CTkLabel(alert_thresholds_frame, text="Seuils d'Alerte Personnalisés", font=customtkinter.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=2, pady=(0,10))

        # Seismic Magnitude
        customtkinter.CTkLabel(alert_thresholds_frame, text="Magnitude Sismique (M) :", anchor="w").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.seismic_mag_entry = customtkinter.CTkEntry(alert_thresholds_frame, width=80)
        self.seismic_mag_entry.insert(0, str(self.alert_seismic_mag))
        self.seismic_mag_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Seismic Depth
        customtkinter.CTkLabel(alert_thresholds_frame, text="Profondeur Sismique (km) [<=] :", anchor="w").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.seismic_depth_entry = customtkinter.CTkEntry(alert_thresholds_frame, width=80)
        self.seismic_depth_entry.insert(0, str(self.alert_seismic_depth))
        self.seismic_depth_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        
        # KP Index
        customtkinter.CTkLabel(alert_thresholds_frame, text="KP-Index (>=) :", anchor="w").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.kp_index_entry = customtkinter.CTkEntry(alert_thresholds_frame, width=80)
        self.kp_index_entry.insert(0, str(self.alert_kp_index))
        self.kp_index_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

        # CME Speed
        customtkinter.CTkLabel(alert_thresholds_frame, text="Vitesse CME (km/s) [>=] :", anchor="w").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.cme_speed_entry = customtkinter.CTkEntry(alert_thresholds_frame, width=80)
        self.cme_speed_entry.insert(0, str(self.alert_cme_speed))
        self.cme_speed_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")

        # NEO Distance (Lunar Distances)
        customtkinter.CTkLabel(alert_thresholds_frame, text="Distance NEO (LD) [<=] :", anchor="w").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        self.neo_distance_entry = customtkinter.CTkEntry(alert_thresholds_frame, width=80)
        self.neo_distance_entry.insert(0, str(self.alert_neo_distance_ld))
        self.neo_distance_entry.grid(row=5, column=1, padx=5, pady=5, sticky="ew")


        # Save Settings Button
        save_settings_button = customtkinter.CTkButton(settings_frame, text="Appliquer et Enregistrer Paramètres", command=self.apply_and_save_settings)
        save_settings_button.grid(row=6, column=0, columnspan=2, padx=10, pady=20)


    def change_appearance_mode_event(self, new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)

    def change_color_theme_event(self, new_color_theme: str):
        customtkinter.set_default_color_theme(new_color_theme)

    def apply_and_save_settings(self):
        try:
            self.alert_seismic_mag = float(self.seismic_mag_entry.get())
            self.alert_seismic_depth = float(self.seismic_depth_entry.get())
            self.alert_kp_index = int(self.kp_index_entry.get())
            self.alert_cme_speed = int(self.cme_speed_entry.get())
            self.alert_neo_distance_ld = float(self.neo_distance_entry.get())

            self.save_settings() 
            self.toggle_map_overlays() 
            
        except ValueError:
            messagebox.showerror("Erreur de Saisie", "Veuillez entrer des valeurs numériques valides pour les seuils.")

    # ==================== OUTILS GENERAUX ====================
    def export_log_to_csv(self, treeview_widget, filename):
        if not self.winfo_exists(): return
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=filename,
                                               filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not filepath: return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                columns_ids = treeview_widget['columns']
                
                export_cols = []
                export_headers = []
                for col_id in columns_ids:
                    heading_text = treeview_widget.heading(col_id, 'text')
                    column_width = treeview_widget.column(col_id, 'width')
                    
                    if column_width > 0 or col_id in ['Link', 'Lat', 'Lon']:
                        export_headers.append(heading_text if heading_text else col_id)
                        export_cols.append(col_id)

                writer.writerow(export_headers)

                for child_id in treeview_widget.get_children():
                    item_values = treeview_widget.item(child_id, 'values')
                    
                    export_row = []
                    for col_id in export_cols:
                        try:
                            original_index = columns_ids.index(col_id)
                            export_row.append(item_values[original_index])
                        except ValueError:
                            export_row.append("")
                    writer.writerow(export_row)

            messagebox.showinfo("Exportation Réussie", f"Le journal a été exporté vers {filepath}")
        except Exception as e:
            messagebox.showerror("Erreur d'Exportation", f"Une erreur est survenue lors de l'exportation du journal: {e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()