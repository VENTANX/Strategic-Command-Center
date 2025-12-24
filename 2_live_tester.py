# ==============================================================================
# PROJECT: 2 - Live Tester on Seismic API
# Author: OUSSAMA ASLOUJ
# ==============================================================================
import requests
import pandas as pd
import numpy as np
import joblib

# ------------------------------------------------------------------------------
# 1. Charger le modèle et le scaler précédemment sauvegardés
# ------------------------------------------------------------------------------
print("--- Chargement du modèle et du scaler pré-entraînés ---")
try:
    model = joblib.load('anomaly_detector_model.joblib')
    scaler = joblib.load('data_scaler.joblib')
    print("Modèle et scaler chargés avec succès.")
except FileNotFoundError:
    print("ERREUR : Fichiers .joblib introuvables. Veuillez d'abord lancer '1_train_model.py'.")
    exit()

# ------------------------------------------------------------------------------
# 2. Interroger l'API de l'USGS pour obtenir les derniers séismes
# ------------------------------------------------------------------------------
# On va chercher les séismes de magnitude 4.5+ des dernières 24h
url_usgs = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson'

print(f"\n--- Interrogation de l'API de l'USGS... ---")
try:
    response = requests.get(url_usgs)
    response.raise_for_status()
    live_data = response.json()
    print(f"Succès ! {len(live_data['features'])} événements sismiques de M4.5+ récupérés.")
except requests.exceptions.RequestException as e:
    print(f"ERREUR : Impossible de contacter l'API de l'USGS. {e}")
    exit()

# ------------------------------------------------------------------------------
# 3. Traiter les données de l'API et faire des prédictions
# ------------------------------------------------------------------------------
events_to_test = []
event_details = []

for event in live_data['features']:
    properties = event['properties']
    geometry = event['geometry']

    # L'API fournit la magnitude ('mag') et la profondeur ('depth')
    mag = properties.get('mag')
    depth = geometry['coordinates'][2] # La profondeur est la 3ème coordonnée

    if mag is not None and depth is not None:
        events_to_test.append([depth, mag])
        event_details.append(f"Lieu: {properties.get('place', 'N/A')}, Magnitude: {mag}, Profondeur: {depth} km")

if not events_to_test:
    print("\n--- Aucun événement récent avec les données de profondeur/magnitude n'a été trouvé. ---")
    exit()

# Créer un DataFrame et normaliser les données avec le scaler CHARGÉ
X_live = pd.DataFrame(events_to_test, columns=['Depth', 'Magnitude'])
X_live_scaled = scaler.transform(X_live)

# Faire la prédiction avec notre modèle CHARGÉ
predictions = model.predict(X_live_scaled)

# ------------------------------------------------------------------------------
# 4. Afficher les résultats
# ------------------------------------------------------------------------------
print("\n--- RÉSULTATS DE L'ANALYSE EN DIRECT ---")
for i, prediction in enumerate(predictions):
    print(f"\nÉvénement #{i+1}: {event_details[i]}")
    if prediction == -1:
        print("   >>> ALERTE : ACTIVITÉ ANORMALE DÉTECTÉE ! <<<")
        print("   >>> Signature (profondeur/magnitude) INCOMPATIBLE avec un séisme typique. <<<")
    else:
        print("   --> Statut : Normal. Signature compatible avec un séisme.")