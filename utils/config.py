"""
@file config.py
@brief Modul zum sicheren Lesen, Schreiben und Validieren der zentralen config.toml
"""

import os
import toml
from threading import Lock
from pathlib import Path

# Absoluter Pfad zur zentralen Konfigurationsdatei berechnen
CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.toml'))

# Lock für Thread-Sicherheit beim gleichzeitigen Zugriff auf die Datei
_lock = Lock()

# Erforderliche Felder und ihre erwarteten Typen in der Konfigurationsdatei
REQUIRED_FIELDS = {
    "handle": str,        # Benutzername
    "port": int,          # Lokaler Port für Netzwerkkommunikation
    "whoisport": int,     # Port für WHOIS-Broadcast
    "autoreply": str,     # Abwesenheitsnachricht
    "imagepath": str,     # Speicherort für empfangene Bilder
    "dark_mode": bool     # Dark-Mode für GUI (optional hinzugefügt)
}


## \brief Lädt und validiert die Konfigurationsdatei.
#  \details Öffnet die zentrale config.toml-Datei, prüft auf Existenz, Vollständigkeit und Datentypen.
#  Erstellt bei Bedarf automatisch den Zielordner für empfangene Bilder.
#  \return Dictionary mit allen Konfigurationswerten
#  \throws FileNotFoundError wenn die Datei fehlt
#  \throws ValueError bei fehlenden oder falsch typisierten Einträgen
def load_config() -> dict:
    """
    Lädt und validiert die Konfigurationsdatei.
    @return: Dictionary mit Konfigurationswerten
    @raises FileNotFoundError: wenn config.toml fehlt
    @raises ValueError: wenn ein Feld fehlt oder falschen Typ hat
    """
    with _lock:
        if not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {CONFIG_PATH}")

        # Datei öffnen und parsen (TOML-Format)
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = toml.load(f)

        # Validierung aller Pflichtfelder
        for key, typ in REQUIRED_FIELDS.items():
            if key not in config:
                raise ValueError(f"Fehlender Eintrag in config.toml: {key}")
            if not isinstance(config[key], typ):
                raise ValueError(f"Ungültiger Typ für '{key}': erwartet {typ.__name__}")

        # Sicherstellen, dass der Bilderordner existiert
        Path(config["imagepath"]).mkdir(parents=True, exist_ok=True)

        return config


## \brief Speichert ein vollständiges Konfigurations-Dictionary in die config.toml.
#  \details Diese Funktion überschreibt die bestehende Datei mit dem neuen Inhalt.
#  \param new_config Das neue Konfigurationsdictionary mit allen Werten
def save_config(new_config: dict):
    """
    Speichert die übergebene Konfiguration sicher in die Datei.
    @param new_config: Dictionary mit gültigen Konfigurationswerten
    """
    with _lock:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            toml.dump(new_config, f)


## \brief Aktualisiert ein einzelnes Feld in der Konfiguration.
#  \details Liest die Konfiguration, verändert den angegebenen Wert und speichert sie neu.
#  \param key Der Name des zu ändernden Feldes (z. B. "handle")
#  \param value Der neue Wert (muss vom richtigen Typ sein)
#  \throws ValueError Wenn das Feld nicht bekannt oder vom falschen Typ ist
def update_config_field(key: str, value):
    """
    Aktualisiert ein einzelnes Feld in der Konfigurationsdatei.
    @param key: Name des Feldes
    @param value: Neuer Wert
    @raises ValueError: bei ungültigem Feld oder Typ
    """
    if key not in REQUIRED_FIELDS:
        raise ValueError(f"Unbekanntes Feld: {key}")

    if not isinstance(value, REQUIRED_FIELDS[key]):
        raise ValueError(f"Falscher Typ für {key}: erwartet {REQUIRED_FIELDS[key].__name__}")

    config = load_config()
    config[key] = value
    save_config(config)


## \brief Gibt den aktuellen Wert eines einzelnen Konfigurationsfeldes zurück.
#  \param key Der Name des Feldes (z. B. "handle", "port", "dark_mode")
#  \return Der aktuelle Wert des Feldes oder None, wenn nicht gefunden
def get_config_value(key: str):
    """
    Gibt einen einzelnen Konfigurationswert zurück.
    @param key: Feldname
    @return: Aktueller Wert
    """
    config = load_config()
    return config.get(key)