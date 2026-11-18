#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <SPI.h>
#include <MFRC522.h>
#include <time.h>

// ==============================
// WIFI
// ==============================
const char* ssid = "HONOR X7c";
const char* password = "00000000";

// ⚠️ IP de ton PC (Flask) - À modifier selon ton réseau
const char* serverName = "http://10.119.195.50:5000/data";

// ==============================
// Configuration NTP (heure réelle)
// ==============================
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 3600;  // UTC+1 pour Tunisie
const int daylightOffset_sec = 0;

// ==============================
// DHT11
// ==============================
#define DHTPIN 27
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);


// ==============================
// PIR (détecteur de mouvement)
// ==============================
#define PIR_PIN 13

// ==============================
// RFID
// ==============================
#define SS_PIN 5
#define RST_PIN 22
MFRC522 rfid(SS_PIN, RST_PIN);

// ==============================
// Variables pour anti-rebond RFID
// ==============================
unsigned long lastRFIDRead = 0;
const unsigned long rfidCooldown = 5000;  // 5 secondes entre deux lectures

// ==============================
// Variables pour gestion PIR
// ==============================
unsigned long lastPIRRead = 0;
const unsigned long pirCooldown = 2000;  // 2 secondes entre deux lectures
int lastPIRState = LOW;

// ==============================
// SETUP
// ==============================
void setup() {
  Serial.begin(115200);

  // Initialisation capteurs
  dht.begin();
  pinMode(PIR_PIN, INPUT);

  // Initialisation RFID
  SPI.begin();
  rfid.PCD_Init();
  Serial.println("📡 RFID initialisé");

  // Connexion WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connexion WiFi");

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ Connecté !");
    Serial.print("IP ESP32: ");
    Serial.println(WiFi.localIP());

    // Configuration NTP
    Serial.print("Synchronisation NTP");
    configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);

    // Attendre la synchronisation
    struct tm timeinfo;
    int ntpAttempts = 0;
    while (!getLocalTime(&timeinfo) && ntpAttempts < 10) {
      Serial.print(".");
      delay(1000);
      ntpAttempts++;
    }

    if (ntpAttempts < 10) {
      Serial.println("\n✅ Heure synchronisée !");
      char timeStringBuff[50];
      strftime(timeStringBuff, sizeof(timeStringBuff), "%H:%M:%S", &timeinfo);
      Serial.print("Heure actuelle: ");
      Serial.println(timeStringBuff);
    } else {  
      Serial.println("\n⚠️ Échec synchronisation NTP, utilisation de l'heure système");
    }
  } else {
    Serial.println("\n❌ Échec connexion WiFi");
  }
}

// ==============================
// Fonction pour obtenir l'heure formatée
// ==============================
String getFormattedTime() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    // Si NTP échoue, utiliser millis() comme fallback
    int h = (millis() / 3600000) % 24;
    int m = (millis() / 60000) % 60;
    char fallback[6];
    sprintf(fallback, "%02d:%02d", h, m);
    return String(fallback);
  }

  char timeString[6];
  strftime(timeString, sizeof(timeString), "%H:%M", &timeinfo);
  return String(timeString);
}

// ==============================
// Lecture RFID avec anti-rebond
// ==============================
int readRFID() {
  // Anti-rebond: éviter les lectures trop fréquentes
  if (millis() - lastRFIDRead < rfidCooldown) {
    return 0;
  }

  if (!rfid.PICC_IsNewCardPresent()) return 0;
  if (!rfid.PICC_ReadCardSerial()) return 0;

  // Lecture réussie
  Serial.println("📡 Carte RFID détectée");

  // Afficher l'UID de la carte
  Serial.print("UID: ");
  for (byte i = 0; i < rfid.uid.size; i++) {
    Serial.print(rfid.uid.uidByte[i] < 0x10 ? " 0" : " ");
    Serial.print(rfid.uid.uidByte[i], HEX);
  }
  Serial.println();

  // Arrêter la lecture de la carte
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();

  lastRFIDRead = millis();
  return 1;
}

// ==============================
// Lecture PIR avec anti-rebond
// ==============================
int readPIR() {
  int currentState = digitalRead(PIR_PIN);

  // Détecter uniquement les changements d'état (front montant)
  if (currentState == HIGH && lastPIRState == LOW && (millis() - lastPIRRead > pirCooldown)) {
    lastPIRState = HIGH;
    lastPIRRead = millis();
    Serial.println("🚶 Mouvement détecté !");
    return 1;
  } else if (currentState == LOW) {
    lastPIRState = LOW;
  }

  return 0;
}

// ==============================
// LOOP PRINCIPAL
// ==============================
void loop() {
  // Vérifier la connexion WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ WiFi déconnecté, tentative de reconnexion...");
    WiFi.reconnect();
    delay(5000);
    return;
  }

  HTTPClient http;

  // Lire les capteurs
  float temperature = dht.readTemperature();
  float humidite = dht.readHumidity();

  // Vérifier si les lectures DHT sont valides
  if (isnan(temperature) || isnan(humidite)) {
    Serial.println("❌ Erreur lecture DHT11, utilisation des dernières valeurs valides");
    // Garder les dernières valeurs valides ou utiliser 0
    static float lastTemp = 0;
    static float lastHum = 0;
    if (temperature == 0) temperature = lastTemp;
    if (humidite == 0) humidite = lastHum;
  }

  int pir = readPIR();        // Valeur 0 ou 1 (détection mouvement)
  int rfid_val = readRFID();  // Valeur 0 ou 1 (carte détectée)

  // Obtenir l'heure réelle
  String heure = getFormattedTime();

  // ==============================
  // AFFICHAGE SERIAL
  // ==============================
  Serial.println("\n===== Données capteurs =====");
  Serial.print("🌡️ Température : ");
  Serial.print(temperature);
  Serial.println(" °C");
  Serial.print("💧 Humidité    : ");
  Serial.print(humidite);
  Serial.println(" %");
  Serial.print("🚶 PIR         : ");
  Serial.println(pir ? "Mouvement" : "Aucun");
  Serial.print("🔑 RFID        : ");
  Serial.println(rfid_val ? "Carte détectée" : "Aucune");
  Serial.print("⏰ Heure       : ");
  Serial.println(heure);

  // ==============================
  // Construction JSON (compatible avec Flask)
  // ==============================
  String json = "{";
  json += "\"temperature\":" + String(temperature, 1) + ",";
  json += "\"humidite\":" + String(humidite, 1) + ",";
  json += "\"valeur_du_pir\":" + String(pir) + ",";
  json += "\"valeur_du_rfid\":" + String(rfid_val) + ",";
  json += "\"heure\":\"" + heure + "\"";
  json += "}";

  Serial.println("\n📤 JSON envoyé au serveur :");
  Serial.println(json);

  // ==============================
  // ENVOI HTTP
  // ==============================
  http.begin(serverName);
  http.addHeader("Content-Type", "application/json");

  int httpResponseCode = http.POST(json);

  Serial.print("📡 Code HTTP : ");
  Serial.println(httpResponseCode);

  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.println("📩 Réponse du serveur :");
    Serial.println(response);

    // Analyser la réponse JSON (simple)
    if (response.indexOf("\"ventilation\":\"ON\"") != -1) {
      Serial.println("💨 Ventilation : ON");
    } else if (response.indexOf("\"ventilation\":\"OFF\"") != -1) {
      Serial.println("🛑 Ventilation : OFF");
    }

    // Afficher le compteur de personnes
    int personnesIndex = response.indexOf("\"personnes\":");
    if (personnesIndex != -1) {
      int start = personnesIndex + 12;
      int end = response.indexOf(",", start);
      if (end == -1) end = response.indexOf("}", start);
      String personnes = response.substring(start, end);
      Serial.print("👥 Nombre de personnes : ");
      Serial.println(personnes);
    }

  } else {
    Serial.print("❌ Erreur envoi : ");
    Serial.println(httpResponseCode);
  }

  http.end();

  // Attendre avant la prochaine lecture (1 minute)
  Serial.println("⏱️ Attente 60 secondes...\n");
  delay(60000);
}