import firebase_admin
from firebase_admin import credentials, db
import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(script_dir, "firebase-key.json")

cred = credentials.Certificate(cred_path)

firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://smartclassroomai-ae608-default-rtdb.firebaseio.com'
})

ref = db.reference("smart_classroom")

data = {
    "temperature": 25,
    "humidite": 60,
    "pir": 1,
    "rfid": 1,
    "personnes": 1,
    "heure": "14:30",
    "temp_future": 26.5,
    "ventilation": "OFF"
}

ref.push(data)

print("✅ Firebase fonctionne !")