from flask import Flask, request, jsonify, send_from_directory
import joblib
import pandas as pd
import firebase_admin
from firebase_admin import credentials, db, firestore
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ==============================
# MODELE ML
# ==============================
base_dir = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(base_dir, "les pages web 2")

@app.route("/")
def accueil():
    return send_from_directory(PAGES_DIR, "Accueil.html")

@app.route("/login")
def login():
    return send_from_directory(PAGES_DIR, "login.html")

@app.route("/dashboard")
def dashboard():
    return send_from_directory(PAGES_DIR, "dashboard.html")

@app.route("/historique")
def historique():
    return send_from_directory(PAGES_DIR, "historique.html")

@app.route("/admin")
def admin():
    return send_from_directory(PAGES_DIR, "1.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(PAGES_DIR, filename)


model_path = os.path.join(base_dir, "ridge_model.pkl")
if not os.path.exists(model_path):
    raise FileNotFoundError(f"Modèle introuvable : {model_path}")

model = joblib.load(model_path)
print("Modèle chargé avec succès")

# ==============================
# FIREBASE
# ==============================
firebase_key_path = os.path.join(base_dir, "firebase-key.json")

if not os.path.exists(firebase_key_path):
    raise FileNotFoundError(f"Clé Firebase introuvable : {firebase_key_path}")

if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_key_path)
    firebase_admin.initialize_app(cred, {
       'databaseURL': 'https://smartclassroomai-f4ffe-default-rtdb.europe-west1.firebasedatabase.app'
    })
    print("Firebase initialisé")

rt_db = db.reference("smart_classroom")
compteur_ref = db.reference("compteur")
commandes_ref = db.reference("commandes")
fs_db = firestore.client()

try:
    if compteur_ref.child("personnes").get() is None:
        compteur_ref.child("personnes").set(0)
    if commandes_ref.child("ventilation").get() is None:
        commandes_ref.child("ventilation").set("OFF")
    if commandes_ref.child("mode_auto").get() is None:
        commandes_ref.child("mode_auto").set(True)  # Mode automatique par défaut
except Exception as e:
    print(f"Avertissement : {e}")

# ==============================
# FONCTION DE VENTILATION AUTOMATIQUE
# ==============================
def get_auto_ventilation_settings():
    try:
        settings_doc = fs_db.collection("settings").document("ventilation_auto").get()
        if settings_doc.exists:
            return settings_doc.to_dict()
        else:
            # Paramètres par défaut
            default_settings = {
                "enabled": True,
                "temp_on_threshold": 26.0,
                "temp_off_threshold": 24.0,
                "humidity_on_threshold": 70.0,
                "humidity_off_threshold": 60.0,
                "cooldown_seconds": 60
            }
            fs_db.collection("settings").document("ventilation_auto").set(default_settings)
            return default_settings
    except Exception as e:
        print(f"Erreur chargement paramètres ventilation auto: {e}")
        return {
            "enabled": True,
            "temp_on_threshold": 26.0,
            "temp_off_threshold": 24.0,
            "humidity_on_threshold": 70.0,
            "humidity_off_threshold": 60.0,
            "cooldown_seconds": 60
        }

def update_ventilation_auto(temperature, humidite):
    """Met à jour l'état de la ventilation en fonction des paramètres automatiques"""
    try:
        settings = get_auto_ventilation_settings()
        mode_auto = commandes_ref.child("mode_auto").get()
        
        # Si le mode automatique est désactivé, ne pas modifier
        if not mode_auto:
            return commandes_ref.child("ventilation").get()
        
        if not settings.get("enabled", True):
            return commandes_ref.child("ventilation").get()
        
        current_state = commandes_ref.child("ventilation").get()
        current_state = current_state == "ON"
        
        temp_on = settings.get("temp_on_threshold", 26.0)
        temp_off = settings.get("temp_off_threshold", 24.0)
        hum_on = settings.get("humidity_on_threshold", 70.0)
        hum_off = settings.get("humidity_off_threshold", 60.0)
        
        new_state = current_state
        
        # Logique de décision
        if not current_state:
            # Ventilation éteinte → on vérifie si on doit l'allumer
            if temperature >= temp_on or humidite >= hum_on:
                new_state = True
                print(f"🌬️ Ventilation AUTO activée (Temp: {temperature}°C / Hum: {humidite}%)")
        else:
            # Ventilation allumée → on vérifie si on doit l'éteindre
            if temperature <= temp_off and humidite <= hum_off:
                new_state = False
                print(f"🌬️ Ventilation AUTO désactivée (Temp: {temperature}°C / Hum: {humidite}%)")
        
        if new_state != current_state:
            new_state_str = "ON" if new_state else "OFF"
            commandes_ref.child("ventilation").set(new_state_str)
            # Log de l'action
            fs_db.collection("activity_log").add({
                "type": "ventilation_auto",
                "msg": f"Ventilation automatique {new_state_str} (Temp: {temperature}°C, Hum: {humidite}%)",
                "who": "système",
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            return new_state_str
        
        return "ON" if current_state else "OFF"
        
    except Exception as e:
        print(f"Erreur ventilation auto: {e}")
        return commandes_ref.child("ventilation").get()

# ==============================
# ROUTE : Données capteurs
# ==============================
@app.route("/data", methods=["POST"])
def receive_data():
    try:
        data = request.get_json()

        required_fields = ["temperature", "humidite", "valeur_du_pir", "valeur_du_rfid", "heure"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Champ manquant : {field}"}), 400

        temperature = float(data["temperature"])
        humidite    = float(data["humidite"])
        pir         = int(data["valeur_du_pir"])
        rfid        = int(data["valeur_du_rfid"])
        heure       = data["heure"]

        # Préparation pour le modèle
        time    = pd.to_datetime(heure, format="%H:%M")
        minutes = time.hour * 60 + time.minute
        df = pd.DataFrame([[temperature, humidite, pir, rfid, minutes]],
                          columns=model.feature_names_in_)

        temp_future = model.predict(df)[0]
        
        # ==============================
        # VENTILATION AUTOMATIQUE
        # ==============================
        ventilation = update_ventilation_auto(temperature, humidite)
        
        # ==============================
        # COMPTEUR AUTOMATIQUE VIA RFID
        # ==============================
        personnes = compteur_ref.child("personnes").get()
        if personnes is None:
            personnes = 0

        if rfid == 1:
            personnes += 1
            compteur_ref.child("personnes").set(personnes)
            print(f"RFID détecté → Entrée automatique → {personnes} personne(s)")

        # Écriture Firebase Realtime DB
        rt_db.push({
            "temperature": temperature,
            "humidite":    humidite,
            "pir":         pir,
            "rfid":        rfid,
            "heure":       heure,
            "temp_future": round(float(temp_future), 2),
            "ventilation": ventilation,
            "personnes":   personnes
        })
        
        # Écriture Firestore (historique)
        fs_db.collection("historique").add({
            "temperature": temperature,
            "humidite":    humidite,
            "personnes":   personnes,
            "heure":       heure,
            "temp_future": round(float(temp_future), 2),
            "timestamp":   firestore.SERVER_TIMESTAMP,
            "pir":         pir,
            "rfid":        rfid,
            "ventilation": ventilation
        })
        
        return jsonify({
            "temp_future": round(float(temp_future), 2),
            "ventilation": ventilation,
            "personnes":   personnes
        })
        
    except ValueError as e:
        return jsonify({"error": f"Valeur invalide : {str(e)}"}), 400
    except Exception as e:
        print(f"ERREUR : {e}")
        return jsonify({"error": str(e)}), 500

# ==============================
# ROUTE : Compteur manuel
# ==============================
@app.route("/update", methods=["POST"])
def update_people():
    try:
        data   = request.get_json()
        action = data.get("action")
        if action not in ["IN", "OUT"]:
            return jsonify({"error": "Action invalide. Utilisez 'IN' ou 'OUT'."}), 400

        current = compteur_ref.child("personnes").get()
        if current is None:
            current = 0
        if action == "IN":
            current += 1
        elif action == "OUT":
            current -= 1
        if current < 0:
            current = 0
        compteur_ref.child("personnes").set(current)
        return jsonify({"personnes": current, "action": action})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==============================
# ROUTE : Contrôle ventilation
# ==============================
@app.route("/ventilation", methods=["POST"])
def control_ventilation():
    try:
        data = request.get_json()
        state = data.get("state")
        mode_auto = data.get("mode_auto")
        
        if state is not None and state in ["ON", "OFF"]:
            commandes_ref.child("ventilation").set(state)
            # Désactiver le mode auto quand on contrôle manuellement
            commandes_ref.child("mode_auto").set(False)
            
            fs_db.collection("activity_log").add({
                "type": "ventilation",
                "msg": f"Ventilation manuelle {state}",
                "who": data.get("user", "inconnu"),
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            return jsonify({"ventilation": state, "mode_auto": False})
        
        elif mode_auto is not None:
            commandes_ref.child("mode_auto").set(mode_auto)
            fs_db.collection("activity_log").add({
                "type": "ventilation",
                "msg": f"Mode ventilation automatique {'activé' if mode_auto else 'désactivé'}",
                "who": data.get("user", "inconnu"),
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            return jsonify({"mode_auto": mode_auto})
        
        return jsonify({"error": "Paramètre invalide"}), 400
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==============================
# ROUTE : Paramètres ventilation automatique
# ==============================
@app.route("/ventilation/settings", methods=["GET", "POST"])
def ventilation_settings():
    if request.method == "GET":
        try:
            settings = fs_db.collection("settings").document("ventilation_auto").get()
            if settings.exists:
                return jsonify(settings.to_dict())
            else:
                default = {
                    "enabled": True,
                    "temp_on_threshold": 26.0,
                    "temp_off_threshold": 24.0,
                    "humidity_on_threshold": 70.0,
                    "humidity_off_threshold": 60.0,
                    "cooldown_seconds": 60
                }
                return jsonify(default)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    elif request.method == "POST":
        try:
            settings = request.get_json()
            required = ["temp_on_threshold", "temp_off_threshold", "humidity_on_threshold", "humidity_off_threshold"]
            
            for key in required:
                if key not in settings:
                    return jsonify({"error": f"Champ manquant: {key}"}), 400
            
            # Validation des seuils
            if settings["temp_on_threshold"] <= settings["temp_off_threshold"]:
                return jsonify({"error": "Le seuil d'activation doit être supérieur au seuil de désactivation"}), 400
            
            if settings["humidity_on_threshold"] <= settings["humidity_off_threshold"]:
                return jsonify({"error": "Le seuil d'activation humidité doit être supérieur au seuil de désactivation"}), 400
            
            fs_db.collection("settings").document("ventilation_auto").set(settings)
            
            # Log
            fs_db.collection("activity_log").add({
                "type": "settings",
                "msg": f"Paramètres ventilation auto modifiés: ON à {settings['temp_on_threshold']}°C, OFF à {settings['temp_off_threshold']}°C",
                "who": request.json.get("user", "système"),
                "timestamp": firestore.SERVER_TIMESTAMP
            })
            
            return jsonify({"success": True, "settings": settings})
            
        except Exception as e:
            return jsonify({"error": str(e)}), 500

# ==============================
# ROUTE : Test de santé
# ==============================
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

# ==============================
# LANCEMENT
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)