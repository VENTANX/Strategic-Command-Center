# ==============================================================================
# PROJECT: 2 - Tsunami Prediction Model Training (from File)
# Author: OUSSAMA ASLOUJ
# ==============================================================================
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

print("--- Étape 1 : Chargement et Nettoyage du Fichier 'tsunami_dataset.csv' ---")

try:
    # On ne lit que les colonnes qui nous intéressent pour être plus efficace et éviter les erreurs
    use_cols = ['EQ_MAGNITUDE', 'EQ_DEPTH', 'TS_INTENSITY']
    data = pd.read_csv('tsunami_dataset.csv', usecols=use_cols)
except FileNotFoundError:
    print("ERREUR : Le fichier 'tsunami_dataset.csv' est introuvable. Assurez-vous qu'il est dans le même dossier que ce script.")
    exit()
except ValueError as e:
    print(f"ERREUR : Le fichier CSV semble avoir un problème de colonnes. Vérifiez que les colonnes {use_cols} existent bien. Détail: {e}")
    exit()

# Nettoyer les données : supprimer les lignes où nos colonnes clés sont vides
data.dropna(subset=['EQ_MAGNITUDE', 'EQ_DEPTH', 'TS_INTENSITY'], inplace=True)

print(f"Données nettoyées. {len(data)} événements utilisables trouvés dans le fichier.")

# Création de la variable cible : si l'intensité du tsunami est > 0, alors un tsunami a eu lieu (1). Sinon (0).
data['TSUNAMI_EVENT'] = (data['TS_INTENSITY'] > 0).astype(int)

print("\nDistribution de la variable cible 'TSUNAMI_EVENT':")
print(data['TSUNAMI_EVENT'].value_counts())

# Définir les features et la cible
features = ['EQ_DEPTH', 'EQ_MAGNITUDE']
target = 'TSUNAMI_EVENT'
X = data[features]
y = data[target]

# Diviser les données
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)

print("\n--- Étape 2 : Entraînement du Modèle RandomForest ---")
model = RandomForestClassifier(n_estimators=100, random_state=42, class_weight='balanced')
model.fit(X_train, y_train)

print("Modèle de prédiction de tsunami entraîné avec succès.")

print("\n--- Étape 3 : Évaluation du Modèle ---")
predictions = model.predict(X_test)
print("Rapport de classification sur les données de test :")
print(classification_report(y_test, predictions, zero_division=0))

print("\n--- Étape 4 : Sauvegarde du Modèle ---")
joblib.dump(model, 'tsunami_predictor_model.joblib')
print("Modèle sauvegardé dans 'tsunami_predictor_model.joblib'")
print("\nProcessus d'entraînement du modèle de tsunami terminé. Vous pouvez maintenant lancer l'application principale.")