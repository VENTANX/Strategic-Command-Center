# ==============================================================================
# PROJECT: Command Center - Final, Complete and Stable Version
# Author: OUSSAMA ASLOUJ
# ==============================================================================
import tkinter
from tkinter import ttk, messagebox, filedialog
import customtkinter
import tkintermapview
import requests
import pandas as pd
import joblib
from datetime import datetime, timedelta
import webbrowser
import re
from shapely.geometry import Point, Polygon
import threading
import feedparser

# --- CONFIGURATION ---
RISK_ZONES = {"Site d'essais NK": Polygon([(41.4, 129.0), (41.4, 129.2), (41.2, 129.2), (41.2, 129.0)])}
GDACS_RSS_URL = "https://www.gdacs.org/rss.aspx"

customtkinter.set_appearance_mode("Dark")
customtkinter.set_default_color_theme("blue")

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Centre de Commandement et d'Analyse Stratégique")
        self.geometry("1600x900")
        
        self.is_playback_mode = False
        self.processed_event_ids = set()
        
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
        threading.Thread(target=self.initial_data_seed, daemon=True).start()

    def initial_data_seed(self):
        print("Synchronisation initiale des événements sismiques...")
        try:
            url = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson'
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            initial_data = response.json()
            for event in initial_data['features']:
                self.processed_event_ids.add(event['id'])
            print(f"{len(initial_data['features'])} événements existants ont été mémorisés.")
        except requests.exceptions.RequestException as e:
            print(f"Erreur durant la synchronisation initiale: {e}")
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
        self.status_label = customtkinter.CTkLabel(control_frame, text="INITIALISATION...", text_color="yellow", font=customtkinter.CTkFont(weight="bold"))
        self.status_label.pack(side="right", padx=20)
        main_frame = customtkinter.CTkFrame(self.seismic_tab, fg_color="transparent"); main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        map_frame = customtkinter.CTkFrame(main_frame, fg_color="transparent"); map_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        list_frame = customtkinter.CTkFrame(main_frame, width=420); list_frame.pack(side="right", fill="both", expand=False, padx=(5, 0))
        customtkinter.CTkLabel(list_frame, text="Journal des Détections", font=customtkinter.CTkFont(size=16, weight="bold")).pack(pady=10)
        self.map_widget = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
        self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=19)
        self.map_widget.pack(fill="both", expand=True); self.draw_risk_zones()
        style = ttk.Style(); style.theme_use("default"); style.configure("Treeview", background="#2a2d2e", foreground="white", fieldbackground="#2a2d2e", borderwidth=0)
        style.map('Treeview', background=[('selected', '#22559b')]); style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[('active', '#3484F0')])
        self.seismic_log = ttk.Treeview(list_frame, columns=('Time', 'Mag', 'Depth', 'Status'), show='headings')
        self.seismic_log.heading('Time', text='Heure'); self.seismic_log.column('Time', width=80, anchor='center')
        self.seismic_log.heading('Mag', text='Mag.'); self.seismic_log.column('Mag', width=50, anchor='center')
        self.seismic_log.heading('Depth', text='Prof.'); self.seismic_log.column('Depth', width=50, anchor='center')
        self.seismic_log.heading('Status', text='Statut'); self.seismic_log.column('Status', width=180, anchor='w')
        self.seismic_log.pack(fill="both", expand=True, padx=5, pady=5)
        self.seismic_log.tag_configure('normal', foreground='#00FF00'); self.seismic_log.tag_configure('low_anomaly', foreground='orange')
        self.seismic_log.tag_configure('high_anomaly', foreground='red', font=('Calibri', 10, 'bold'))
        self.seismic_log.tag_configure('critical_anomaly', foreground='magenta', font=('Calibri', 10, 'bold', 'underline'))
        self.seismic_log.tag_configure('tsunami_risk', foreground='cyan', font=('Calibri', 10, 'bold'))
        customtkinter.CTkButton(list_frame, text="Exporter en CSV", command=lambda: self.export_log_to_csv(self.seismic_log)).pack(pady=10, padx=5)

    def draw_risk_zones(self):
        self.map_widget.set_position(41.3, 129.1); self.map_widget.set_zoom(7)
        for name, polygon in RISK_ZONES.items():
            self.map_widget.set_polygon(list(polygon.exterior.coords), outline_color="red", fill_color="", name=name)

    def on_marker_click_seismic(self, marker):
        details = marker.data
        info_window = customtkinter.CTkToplevel(self); info_window.title("Détails de l'Événement Sismique"); info_window.geometry("450x220")
        text = (f"Lieu: {details['place']}\n"f"Date/Heure (UTC): {details['time']}\n"f"Magnitude: {details['mag']} | Profondeur: {details['depth']} km\n"f"Statut du modèle: {details['status']}\n"f"{details.get('yield', '')}")
        customtkinter.CTkLabel(info_window, text=text, justify=tkinter.LEFT, wraplength=430).pack(pady=10, padx=10, fill="both", expand=True)
        customtkinter.CTkButton(info_window, text="Ouvrir sur le site de l'USGS", command=lambda: webbrowser.open_new_tab(details['url'])).pack(pady=10)

    def is_in_risk_zone(self, lat, lon):
        point = Point(lon, lat);
        for name, zone in RISK_ZONES.items():
            if zone.contains(point): return name
        return None

    def update_seismic_data(self):
        seismic_update_interval = 60000
        if self.is_playback_mode: self.after(seismic_update_interval, self.update_seismic_data); return
        try:
            url = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson'
            response = requests.get(url, timeout=10); response.raise_for_status()
            live_data = response.json(); new_event_count = 0
            for event in reversed(live_data['features']):
                if event['id'] not in self.processed_event_ids:
                    new_event_count += 1; self.processed_event_ids.add(event['id']); self.process_single_seismic_event(event)
            if new_event_count > 0: print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Traitement de {new_event_count} nouvel(s) événement(s) sismique(s).")
        except requests.exceptions.RequestException as e: print(f"Erreur API Sismique: {e}")
        self.after(seismic_update_interval, self.update_seismic_data)
        
    def process_single_seismic_event(self, event, is_playback=False):
        properties, geometry = event['properties'], event['geometry']
        mag, depth, lat, lon = properties.get('mag'), geometry['coordinates'][2], geometry['coordinates'][1], geometry['coordinates'][0]
        if mag is None or depth is None or mag < 0: return
        place_str = properties.get('place');
        if not place_str or place_str == "null": place_str = f"Coordonnées: {lat:.2f}, {lon:.2f}"
        features_anomaly = pd.DataFrame([[depth, mag]], columns=['Depth', 'Magnitude']); features_anomaly_scaled = self.seismic_scaler.transform(features_anomaly)
        anomaly_score = self.seismic_model.decision_function(features_anomaly_scaled)[0]
        features_tsunami = pd.DataFrame([[depth, mag]], columns=['EQ_DEPTH', 'EQ_MAGNITUDE'])
        tsunami_proba = self.tsunami_model.predict_proba(features_tsunami)[0][1]
        is_tsunami_risk = (tsunami_proba > 0.70 and mag > 7.5)
        tsunami_risk_text = f" (Tsunami Prob. {tsunami_proba:.0%})" if is_tsunami_risk else ""
        zone = self.is_in_risk_zone(lat, lon)
        status, color, tag, alert, yield_info = f"Normal{tsunami_risk_text}", "green", "normal", False, ""; alert_title, alert_message = "", ""
        if anomaly_score < -0.01:
            estimated_yield = self.estimate_yield(mag); yield_info = f"\nPuissance Estimée: {estimated_yield}"
            if zone: status, color, tag, alert_title, alert_message, alert = f"CRITIQUE ({zone})", "magenta", "critical_anomaly", "ALERTE CRITIQUE GÉOPOLITIQUE", f"Anomalie forte détectée DANS une zone à haut risque: {zone} !", True
            elif anomaly_score < -0.1: status, color, tag, alert_title, alert_message, alert = "Anomalie Forte", "red", "high_anomaly", "Alerte de Sécurité", "Une signature sismique fortement anormale a été détectée.", True
            else: status, color, tag = "Anomalie Faible", "orange", "low_anomaly"
        elif is_tsunami_risk: status, color, tag, alert_title, alert_message, alert = f"Normal (RISQUE TSUNAMI)", "cyan", "tsunami_risk", "ALERTE TSUNAMI", "Un séisme avec un fort potentiel tsunamigène a été détecté.", True
        if is_tsunami_risk and status.startswith("Normal"): tag = "tsunami_risk"
        details = {'place': place_str, 'time': datetime.fromtimestamp(properties['time']/1000).strftime('%Y-%m-%d %H:%M:%S'), 'mag': f"{mag:.1f}", 'depth': f"{depth:.1f}", 'status': status, 'url': properties.get('url'), 'yield': yield_info.replace('\n', '')}
        marker = self.map_widget.set_marker(lat, lon, text=f"M{details['mag']}", marker_color_circle=color, command=self.on_marker_click_seismic); marker.data = details
        log_entry = (details['time'].split(' ')[1], details['mag'], details['depth'], status); self.seismic_log.insert('', 'end', values=log_entry, tags=(tag,)); self.seismic_log.yview_moveto(1)
        if status != "Normal": marker.final_color = color; self.pulse_marker(marker)
        if alert and not is_playback and self.initial_seismic_load_complete: messagebox.showwarning(alert_title, f"{alert_message}\n\nLieu: {details['place']}{yield_info}")

    def estimate_yield(self, magnitude):
        try: yield_kt=10**(1.25*magnitude-5.5); return f"~{yield_kt*1000:.0f} tonnes" if yield_kt < 1 else f"~{yield_kt:.1f} kilotonnes"
        except: return "N/A"
        
    def pulse_marker(self, marker, steps=10):
        try:
            if steps>0: next_color="white" if marker.marker_color_circle != "white" else marker.final_color; marker.set_marker_color_circle(next_color); self.after(150, lambda: self.pulse_marker(marker, steps - 1))
            else: marker.set_marker_color_circle(marker.final_color)
        except Exception: pass

    def start_playback(self):
        try:
            start_time = datetime(int(self.year_entry.get()), int(self.month_entry.get()), int(self.day_entry.get())); end_time = start_time + timedelta(days=1)
        except ValueError: messagebox.showerror("Erreur de Date", "Veuillez entrer une date valide (AAAA, MM, JJ)."); return
        self.is_playback_mode = True; self.status_label.configure(text="MODE: RELECTURE", text_color="orange")
        self.seismic_log.delete(*self.seismic_log.get_children()); self.map_widget.delete_all_marker(); self.draw_risk_zones()
        try:
            url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime={start_time.strftime('%Y-%m-%d')}&endtime={end_time.strftime('%Y-%m-%d')}"
            response = requests.get(url, timeout=20); response.raise_for_status()
            events = sorted(response.json()['features'], key=lambda e: e['properties']['time'])
            if events: self.playback_next_event(events, 0)
            else: messagebox.showinfo("Info", "Aucun événement trouvé pour cette date."); self.stop_playback()
        except Exception as e: messagebox.showerror("Erreur API", f"Impossible de récupérer les données historiques: {e}"); self.stop_playback()

    def playback_next_event(self, events, index):
        if index >= len(events) or not self.is_playback_mode: self.stop_playback(); return
        self.process_single_seismic_event(events[index], is_playback=True)
        self.after(500, lambda: self.playback_next_event(events, index + 1))

    def stop_playback(self):
        self.is_playback_mode = False; self.status_label.configure(text="SYNCHRONISANT...", text_color="yellow"); threading.Thread(target=self.initial_data_seed, daemon=True).start()
    
    def export_log_to_csv(self, treeview):
        filepath=filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("Fichiers CSV", "*.csv")])
        if not filepath: return
        rows=[treeview.item(item)['values'] for item in treeview.get_children()]
        df=pd.DataFrame(rows, columns=[treeview.heading(c)['text'] for c in treeview['columns']])
        df.to_csv(filepath, index=False); messagebox.showinfo("Exportation Réussie", f"Le journal a été sauvegardé.")

    # ==================== MODULE SOLAIRE ====================
    def setup_solar_tab(self):
        summary_frame = customtkinter.CTkFrame(self.solar_tab, fg_color="transparent"); summary_frame.pack(fill="x", padx=10, pady=10)
        self.solar_summary_label1 = customtkinter.CTkLabel(summary_frame, text="Plus Grande Éruption (48h): --", font=customtkinter.CTkFont(size=15, weight="bold")); self.solar_summary_label1.pack(side="left", padx=20)
        self.solar_summary_label2 = customtkinter.CTkLabel(summary_frame, text="Menaces Géo-effectives: --", font=customtkinter.CTkFont(size=15, weight="bold")); self.solar_summary_label2.pack(side="left", padx=20)
        list_frame = customtkinter.CTkFrame(self.solar_tab, fg_color="transparent"); list_frame.pack(fill="both", expand=True, padx=10, pady=0)
        self.solar_log=ttk.Treeview(list_frame, columns=('Time', 'Class', 'Region', 'Geo-effective'), show='headings')
        self.solar_log.heading('Time', text='Heure Début (UTC)'); self.solar_log.column('Time', width=200); self.solar_log.heading('Class', text='Classe'); self.solar_log.column('Class', width=150)
        self.solar_log.heading('Region', text='Région Solaire'); self.solar_log.column('Region', width=150); self.solar_log.heading('Geo-effective', text='Menace Terre?'); self.solar_log.column('Geo-effective', width=150, anchor='center')
        self.solar_log.pack(fill="both", expand=True, padx=5, pady=5); self.solar_log.tag_configure('geoeffective_x', foreground='red', font=('Calibri', 12, 'bold')); self.solar_log.tag_configure('geoeffective_m', foreground='orange', font=('Calibri', 11, 'bold'))
        customtkinter.CTkButton(list_frame, text="Exporter en CSV", command=lambda: self.export_log_to_csv(self.solar_log)).pack(pady=10)
        
    def is_flare_geoeffective(self, location_string):
        if not location_string: return False
        match=re.search(r'[EW](\d+)', location_string.upper()); return match and int(match.group(1)) < 60

    def update_solar_data(self):
        if self.is_playback_mode: self.after(900000, self.update_solar_data); return
        try:
            end_date, start_date = datetime.utcnow(), datetime.utcnow() - timedelta(days=2)
            url=f"https://api.nasa.gov/DONKI/FLR?startDate={start_date.strftime('%Y-%m-%d')}&endDate={end_date.strftime('%Y-%m-%d')}&api_key=dOyFPhDlFaYMkH5obElJPIGmpU4pvcfiNmsSkgjJ"
            flares=requests.get(url, timeout=10).json(); self.solar_log.delete(*self.solar_log.get_children())
            geo_effective_count = 0; max_flare = ""
            for flare in reversed(flares):
                class_type = flare.get('classType', 'N/A')
                if not max_flare or (class_type and class_type > max_flare): max_flare = class_type
                is_geo=self.is_flare_geoeffective(flare.get('sourceLocation')); geo_text="OUI" if is_geo else "Non"; tag='normal'
                if is_geo and (class_type.startswith('X') or class_type.startswith('M')):
                    geo_effective_count += 1; tag = 'geoeffective_x' if class_type.startswith('X') else 'geoeffective_m'
                self.solar_log.insert('', 'end', values=(flare.get('beginTime', 'N/A'), class_type, flare.get('sourceLocation', 'N/A'), geo_text), tags=(tag,))
            self.solar_summary_label1.configure(text=f"Plus Grande Éruption (48h): {max_flare or 'Aucune'}")
            self.solar_summary_label2.configure(text=f"Menaces Géo-effectives: {geo_effective_count}")
        except Exception as e: print(f"Erreur API Solaire: {e}")
        self.after(900000, self.update_solar_data)

    # ==================== MODULE ASTÉROÏDES ====================
    def setup_asteroid_tab(self):
        summary_frame = customtkinter.CTkFrame(self.asteroid_tab, fg_color="transparent"); summary_frame.pack(fill="x", padx=10, pady=10)
        self.asteroid_summary_label1 = customtkinter.CTkLabel(summary_frame, text="Approche la plus Proche: --", font=customtkinter.CTkFont(size=15, weight="bold")); self.asteroid_summary_label1.pack(side="left", padx=20)
        self.asteroid_summary_label2 = customtkinter.CTkLabel(summary_frame, text="Objet le plus Large: --", font=customtkinter.CTkFont(size=15, weight="bold")); self.asteroid_summary_label2.pack(side="left", padx=20)
        self.asteroid_summary_label3 = customtkinter.CTkLabel(summary_frame, text="Alertes de Risque Élevé: --", font=customtkinter.CTkFont(size=15, weight="bold")); self.asteroid_summary_label3.pack(side="left", padx=20)
        list_frame = customtkinter.CTkFrame(self.asteroid_tab, fg_color="transparent"); list_frame.pack(fill="both", expand=True, padx=10, pady=0)
        self.asteroid_log=ttk.Treeview(list_frame, columns=('Date', 'Name', 'Diameter', 'Distance', 'Risk'), show='headings')
        self.asteroid_log.heading('Date', text='Date Passage'); self.asteroid_log.column('Date', width=180); self.asteroid_log.heading('Name', text='Nom Objet'); self.asteroid_log.column('Name', width=180)
        self.asteroid_log.heading('Diameter', text='Diamètre Est. (m)'); self.asteroid_log.column('Diameter', width=150, anchor='center')
        self.asteroid_log.heading('Distance', text='Distance Passage (km)'); self.asteroid_log.column('Distance', width=180, anchor='center')
        self.asteroid_log.heading('Risk', text='Score Risque'); self.asteroid_log.column('Risk', width=100, anchor='center')
        self.asteroid_log.pack(fill="both", expand=True, padx=5, pady=5)
        self.asteroid_log.tag_configure('low_risk', foreground='yellow'); self.asteroid_log.tag_configure('medium_risk', foreground='orange'); self.asteroid_log.tag_configure('high_risk', foreground='red', font=('Calibri', 10, 'bold'))
        customtkinter.CTkButton(list_frame, text="Exporter en CSV", command=lambda: self.export_log_to_csv(self.asteroid_log)).pack(pady=10)

    def calculate_risk_score(self, diameter_m, dist_km):
        score=0
        if diameter_m > 25 and dist_km < 7500000: score+=1
        if diameter_m > 140: score+=1
        if dist_km < 384400 * 2: score+=1
        if dist_km < 384400: score+=2
        if score >= 4: return "Élevé", "high_risk"
        if score >= 2: return "Modéré", "medium_risk"
        if score > 0: return "Faible", "low_risk"
        return "Nul", "normal"

    def update_asteroid_data(self):
        if self.is_playback_mode: self.after(3600000, self.update_asteroid_data); return
        try:
            url="https://ssd-api.jpl.nasa.gov/cad.api?dist-max=20LD&sort=dist"
            asteroids=requests.get(url, timeout=15).json()
            self.asteroid_log.delete(*self.asteroid_log.get_children())
            closest_approach_name, largest_diameter_name = "--", "--"; closest_dist, largest_diam, high_risk_count = float('inf'), 0, 0
            if int(asteroids.get('count', 0)) > 0:
                for data in asteroids['data']:
                    data_map={field: value for field, value in zip(asteroids['fields'], data)}
                    dist_km=float(data_map.get('dist', 0)) * 149597870.7; h_mag=float(data_map.get('h', 25))
                    diameter_m=(1329/(10**(0.2 * h_mag))) * 1000 if h_mag > 0 else 0
                    if dist_km < closest_dist: closest_dist, closest_approach_name = dist_km, data_map.get('des')
                    if diameter_m > largest_diam: largest_diam, largest_diameter_name = diameter_m, data_map.get('des')
                    risk_text, risk_tag=self.calculate_risk_score(diameter_m, dist_km)
                    if risk_tag == "high_risk": high_risk_count += 1
                    log_entry=(data_map.get('cd'), data_map.get('des'), f"{diameter_m:.0f}", f"{dist_km:,.0f}", risk_text)
                    self.asteroid_log.insert('', 'end', values=log_entry, tags=(risk_tag,))
            self.asteroid_summary_label1.configure(text=f"Approche la plus Proche: {closest_approach_name} ({closest_dist:,.0f} km)")
            self.asteroid_summary_label2.configure(text=f"Objet le plus Large: {largest_diameter_name} (~{largest_diam:.0f} m)")
            self.asteroid_summary_label3.configure(text=f"Alertes de Risque Élevé: {high_risk_count}")
        except Exception as e: print(f"Erreur API Astéroïdes: {e}")
        self.after(3600000, self.update_asteroid_data)

    # ==================== MODULE CATASTROPHES ====================
    def setup_disaster_tab(self):
        list_frame = customtkinter.CTkFrame(self.disaster_tab, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        customtkinter.CTkLabel(list_frame, text="Alertes de Catastrophes Mondiales (GDACS)", font=customtkinter.CTkFont(size=16, weight="bold")).pack(pady=10)
        self.disaster_log = ttk.Treeview(list_frame, columns=('Date', 'Type', 'Pays', 'Niveau'), show='headings')
        self.disaster_log.heading('Date', text='Date'); self.disaster_log.column('Date', width=150)
        self.disaster_log.heading('Type', text='Type de Catastrophe'); self.disaster_log.column('Type', width=150)
        self.disaster_log.heading('Pays', text='Pays/Région'); self.disaster_log.column('Pays', width=200)
        self.disaster_log.heading('Niveau', text='Niveau d\'Alerte'); self.disaster_log.column('Niveau', width=120, anchor='center')
        self.disaster_log.pack(fill="both", expand=True, padx=5, pady=5)
        self.disaster_log.tag_configure('Green', foreground='green')
        self.disaster_log.tag_configure('Orange', foreground='orange', font=('Calibri', 10, 'bold'))
        self.disaster_log.tag_configure('Red', foreground='red', font=('Calibri', 12, 'bold'))
        self.disaster_log.bind("<Double-1>", self.on_disaster_double_click)
        customtkinter.CTkButton(list_frame, text="Exporter en CSV", command=lambda: self.export_log_to_csv(self.disaster_log)).pack(pady=10)
        
    def on_disaster_double_click(self, event):
        item_id = self.disaster_log.focus()
        if not item_id: return
        item = self.disaster_log.item(item_id)
        if item and 'values' in item and len(item['values']) > 0:
            link = item.get('values')[-1] # Le lien est la dernière valeur
            if link and link.startswith('http'):
                webbrowser.open_new_tab(link)

    def update_disaster_data(self):
        disaster_update_interval = 1800000
        if self.is_playback_mode: self.after(disaster_update_interval, self.update_disaster_data); return
        try:
            print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] Récupération des alertes GDACS...")
            feed = feedparser.parse(GDACS_RSS_URL)
            self.disaster_log.delete(*self.disaster_log.get_children())
            
            for entry in feed.entries:
                alert_level = entry.get('gdacs_alertlevel', 'N/A')
                tag = alert_level if alert_level in ['Green', 'Orange', 'Red'] else 'normal'
                link = entry.get('link', '')
                # On cache le lien de la vue, mais on le garde pour le double-clic
                log_entry = (entry.get('published', 'N/A'), entry.get('gdacs_eventtype', 'N/A'), entry.get('gdacs_country', 'N/A'), alert_level, link)
                self.disaster_log.insert('', 'end', values=log_entry, tags=(tag,))
        except Exception as e: print(f"Erreur API GDACS: {e}")
        self.after(disaster_update_interval, self.update_disaster_data)

if __name__ == "__main__":
    app = App()
    app.mainloop()