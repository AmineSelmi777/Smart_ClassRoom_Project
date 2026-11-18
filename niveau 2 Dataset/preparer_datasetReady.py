import pandas as pd

# 📂 Charger dataset
df = pd.read_csv("DATASET.csv")

# 🔍 Vérification
print("Nombre de lignes :", len(df))

# 🎯 Ajouter colonne temp_future (décalage de 10 lignes)
df["temp_future"] = df["temperature"].shift(-10)

# ❌ Supprimer les lignes vides à la fin
df = df.dropna()

# 💾 Sauvegarder nouveau dataset
df.to_csv("dataset_ready.csv", index=False)

print("✅ Colonne temp_future ajoutée avec succès")