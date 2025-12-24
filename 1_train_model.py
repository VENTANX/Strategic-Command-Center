# ==============================================================================
# PROJECT: 1 - Anomaly Detection Model Training
# Author: OUSSAMA ASLOUJ
# ==============================================================================
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

print("--- Étape 1 : Chargement et Préparation des Données ---")
# Charger le jeu de données que vous avez fourni
try:
    data = pd.read_csv('earthquake.csv')
except FileNotFoundError:
    print("ERREUR : Le fichier 'earthquake.csv' est introuvable. Assurez-vous qu'il est dans le même dossier que ce script.")
    exit()

# Sélection des caractéristiques pertinentes : Profondeur et Magnitude
features = ['Depth', 'Magnitude']
data = data[features + ['Type']]

# Supprimer les lignes avec des données manquantes dans nos colonnes de travail
data.dropna(inplace=True)

print("Aperçu des données utilisées :")
print(data.head())

print("\n--- Étape 2 : Analyse Exploratoire des Données ---")
plt.figure(figsize=(10, 7))
sns.scatterplot(data=data, x='Depth', y='Magnitude', hue='Type', style='Type', s=50)
plt.title('Distribution des Événements par Profondeur et Magnitude', fontsize=16)
plt.xlabel('Profondeur (km)', fontsize=12)
plt.ylabel('Magnitude', fontsize=12)
plt.gca().invert_xaxis() 
plt.legend(title='Type d\'événement')
plt.grid(True)
plt.show()

print("\n--- Étape 3 : Entraînement du Modèle ---")
# Le modèle s'entraîne UNIQUEMENT sur les données normales (séismes)
train_data = data[data['Type'] == 'Earthquake']
X_train = train_data[features]

# Normalisation des données
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)

# Calculer le taux de contamination attendu
contamination_rate = len(data[data['Type'] == 'Nuclear Explosion']) / len(data)

# Initialisation et entraînement du modèle IsolationForest
model = IsolationForest(contamination=contamination_rate, random_state=42)
model.fit(X_train_scaled)

print("Modèle de détection d'anomalies entraîné avec succès.")

print("\n--- Étape 4 : Sauvegarde du Modèle et du Scaler ---")
# Sauvegarder le modèle et le scaler pour le script de test
joblib.dump(model, 'anomaly_detector_model.joblib')
joblib.dump(scaler, 'data_scaler.joblib')

print("Modèle sauvegardé dans 'anomaly_detector_model.joblib'")
print("Scaler sauvegardé dans 'data_scaler.joblib'")
print("\nProcessus d'entraînement terminé. Vous pouvez maintenant lancer '2_live_tester.py'.")