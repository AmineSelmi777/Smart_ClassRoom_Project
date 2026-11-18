import requests
import random
import time
from datetime import datetime

url = "http://127.0.0.1:5000/data"

while True:

    # données simulées réalistes
    temperature = round(random.uniform(20, 30), 2)
    humidite = round(random.uniform(40, 80), 2)

    pir = random.randint(0, 1)
    rfid = random.randint(0, 1)

    heure = datetime.now().strftime("%H:%M")

    data = {
        "temperature": temperature,
        "humidite": humidite,
        "valeur_du_pir": pir,
        "valeur_du_rfid": rfid,
        "heure": heure
    }

    print("\n📡 Données envoyées :", data)

    try:
        response = requests.post(url, json=data)
        print("✅ Réponse serveur :", response.json())

    except Exception as e:
        print("❌ Erreur :", e)

    time.sleep(60)  # toutes les 60 secondes