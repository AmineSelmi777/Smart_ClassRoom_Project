#include <DHT.h>
#include <SPI.h>
#include <MFRC522.h>

#define DHTPIN 4
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

#define PIR_PIN 27

#define SS_PIN 5
#define RST_PIN 22
MFRC522 rfid(SS_PIN, RST_PIN);

void setup() {

Serial.begin(115200);

dht.begin();

pinMode(PIR_PIN, INPUT);

SPI.begin();
rfid.PCD_Init();

Serial.println("temperature,humidite,pir,rfid");

}

void loop() {

float temperature = dht.readTemperature();
float humidite = dht.readHumidity();

if (isnan(temperature) || isnan(humidite)) {
Serial.println("Erreur DHT11");
return;
}

int pir_value = digitalRead(PIR_PIN);

int rfid_value = 0;

if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
rfid_value = 1;
}

Serial.print(temperature);
Serial.print(",");
Serial.print(humidite);
Serial.print(",");
Serial.print(pir_value);
Serial.print(",");
Serial.println(rfid_value);

delay(60000);

}