"""
@file config.py
@brief Modul zum sicheren Lesen, Schreiben und dynamischen Verwalten der zentralen config.toml mit mehreren Clients.

Dieses Modul übernimmt folgende Aufgaben:
- Laden und Speichern der zentralen Konfigurationsdatei im TOML-Format
- Verwaltung mehrerer Clients mit dynamischer Portvergabe
- Zugriff auf Default-Werte (autoreply, whoisport, imagepath etc.)
- Thread-sichere Dateioperationen
- Nutzung im SLCP-basierten Peer-to-Peer-Chatprogramm (BSRN-Projekt)
"""

import os
import toml
import socket
from threading import Lock
from pathlib import Path

# Absoluter Pfad zur zentralen Konfigurationsdatei
CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.toml'))

# Thread-Sicherheit bei Dateioperationen
_lock = Lock()


def load_full_config() -> dict:
    """
    @brief Lädt die komplette Konfiguration (inkl. defaults und clients).
    @return Dictionary mit vollständiger TOML-Konfiguration.
    @throws FileNotFoundError wenn Datei nicht existiert.
    """
    with _lock:
        if not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {CONFIG_PATH}")
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return toml.load(f)


def save_full_config(config: dict):
    """
    @brief Speichert die komplette Konfiguration zurück in die Datei.
    @param config Vollständiges Konfig-Dictionary.
    """
    with _lock:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            toml.dump(config, f)


def is_port_available(port: int) -> bool:
    """
    @brief Prüft, ob ein Port aktuell verfügbar ist.
    @param port Zu prüfender Port.
    @return True wenn verfügbar, sonst False.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0


def find_free_port(config: dict) -> int:
    """
    @brief Findet den ersten verfügbaren Port im Bereich aus defaults.port_range.
    @param config Geladenes Konfigurations-Dictionary.
    @return Freier Port im erlaubten Bereich.
    @throws RuntimeError wenn kein Port verfügbar ist.
    """
    port_range = config["defaults"].get("port_range", [5000, 5100])
    used_ports = [c["port"] for c in config.get("clients", [])]
    for port in range(port_range[0], port_range[1] + 1):
        if port not in used_ports and is_port_available(port):
            return port
    raise RuntimeError("Kein freier Port im konfigurierten Bereich verfügbar.")


def get_or_create_client_config(handle: str) -> dict:
    """
    @brief Gibt die Konfiguration für einen Client-Handle zurück oder erstellt eine neue.
    @param handle Gewünschter Benutzername.
    @return Dictionary mit finalen Konfigurationswerten für diesen Client.
    """
    config = load_full_config()

    for client in config.get("clients", []):
        if client["handle"] == handle:
            Path(config["defaults"]["imagepath"]).mkdir(parents=True, exist_ok=True)
            return {
                "handle": client["handle"],
                "port": client["port"],
                "whoisport": config["defaults"]["whoisport"],
                "autoreply": config["defaults"]["autoreply"],
                "imagepath": config["defaults"]["imagepath"],
            }

    # Neue Konfiguration für diesen Client anlegen
    new_port = find_free_port(config)
    new_client = {"handle": handle, "port": new_port}
    if "clients" not in config:
        config["clients"] = []
    config["clients"].append(new_client)
    save_full_config(config)

    Path(config["defaults"]["imagepath"]).mkdir(parents=True, exist_ok=True)

    return {
        "handle": handle,
        "port": new_port,
        "whoisport": config["defaults"]["whoisport"],
        "autoreply": config["defaults"]["autoreply"],
        "imagepath": config["defaults"]["imagepath"]
    }


def load_config(handle: str = None) -> dict:
    """
    @brief Kompatible Ladefunktion für Alt-Code (Defaults oder spezifischer Client).
    @param handle (Optional) Handle für spezifischen Client.
    @return Dictionary mit Standard- oder Handle-spezifischer Konfiguration.
    """
    config = load_full_config()
    defaults = config.get("defaults", {})
    if handle:
        for client in config.get("clients", []):
            if client["handle"] == handle:
                return {
                    "handle": client["handle"],
                    "port": client["port"],
                    "whoisport": defaults["whoisport"],
                    "autoreply": defaults["autoreply"],
                    "imagepath": defaults["imagepath"]
                }
    return defaults


def update_config_field(key: str, value):
    """
    @brief Aktualisiert ein Feld im defaults-Block.
    @param key Feldname (z. B. 'autoreply', 'dark_mode').
    @param value Neuer Wert für das Feld.
    """
    config = load_full_config()
    if "defaults" not in config:
        config["defaults"] = {}
    config["defaults"][key] = value
    save_full_config(config)


def get_config_value(key: str):
    """
    @brief Gibt einen Wert aus defaults zurück.
    @param key Schlüssel (z. B. 'imagepath').
    @return Wert oder None, falls Schlüssel nicht existiert.
    """
    config = load_full_config()
    return config["defaults"].get(key, None)
