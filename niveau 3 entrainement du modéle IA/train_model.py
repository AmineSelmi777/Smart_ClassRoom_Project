import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import joblib

# Charger le dataset
data =pd.read_csv("dataset_ready.csv")

# convertir l'heure en minutes
data["Heure"] = pd.to_datetime(data["Heure"], format="%H:%M")
data["minutes"] = data["Heure"].dt.hour * 60 + data["Heure"].dt.minute

# variables d'entrée
X = data[[
    "temperature",
    "Humidité",
    "Valeur_du_PIR",
    "Valeur_du_RFID",
    "minutes"
]]

# variable cible
y = data["temp_future"]

# séparation 80% train / 20% test
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# création du modèle
model = Ridge(alpha=1.0)

# entraînement
model.fit(X_train, y_train)

# prédictions
y_pred = model.predict(X_test)

# métriques
r2 = r2_score(y_test, y_pred)
mae = mean_absolute_error(y_test, y_pred)
mse = mean_squared_error(y_test, y_pred)
rmse = np.sqrt(mse)

# affichage des résultats
print("\n===== Performance du modèle =====")
print("R² Score :", r2)
print("MAE :", mae)
print("MSE :", mse)
print("RMSE :", rmse)

# sauvegarder le modèle
joblib.dump(model, "ridge_model.pkl")

print("\nModèle sauvegardé : ridge_model.pkl")