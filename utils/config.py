"""
@file config.py
@brief Verwaltet zentral die config.toml für Clients und Defaults (SLCP).
"""

import os, toml, socket
from threading import Lock
from pathlib import Path

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.toml'))
_lock = Lock()

def load_full_config() -> dict:
    """
    @brief Lädt die vollständige Konfigurationsdatei.
    @return Vollständiges Config-Dictionary.
    @throws FileNotFoundError wenn Datei fehlt.
    """
    with _lock:
        if not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError(f"Datei nicht gefunden: {CONFIG_PATH}")
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return toml.load(f)

def save_full_config(config: dict):
    """
    @brief Schreibt die Konfiguration zurück in die Datei.
    @param config Komplette Konfiguration als Dictionary.
    """
    with _lock:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            toml.dump(config, f)

def is_port_available(port: int) -> bool:
    """
    @brief Prüft, ob ein TCP-Port frei ist.
    @param port Zu prüfender Port.
    @return True wenn frei, sonst False.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0

def find_free_port(config: dict) -> int:
    """
    @brief Sucht freien Port im Bereich defaults.port_range.
    @param config Gesamte Konfiguration.
    @return Freier Port oder Fehler.
    """
    prange = config["defaults"].get("port_range", [5000, 5100])
    used = [c["port"] for c in config.get("clients", [])]
    for p in range(prange[0], prange[1] + 1):
        if p not in used and is_port_available(p):
            return p
    raise RuntimeError("Kein freier Port im Bereich verfügbar.")

def get_or_create_client_config(handle: str) -> dict:
    """
    @brief Holt oder erstellt Konfig für Handle.
    @param handle Benutzername.
    @return Vollständige Konfiguration für den Client.
    """
    config = load_full_config()
    for c in config.get("clients", []):
        if c["handle"] == handle:
            break
    else:
        port = find_free_port(config)
        c = {"handle": handle, "port": port}
        config.setdefault("clients", []).append(c)
        save_full_config(config)

    Path(config["defaults"]["imagepath"]).mkdir(parents=True, exist_ok=True)
    d = config["defaults"]
    return {
        "handle": c["handle"],
        "port": c["port"],
        "whoisport": d["whoisport"],
        "autoreply": d["autoreply"],
        "imagepath": d["imagepath"]
    }

def load_config(handle: str = None) -> dict:
    """
    @brief Lädt Defaults oder spezifische Client-Konfig.
    @param handle Optionaler Benutzername.
    @return Dictionary mit Config-Daten.
    """
    config = load_full_config()
    d = config.get("defaults", {})
    if handle:
        for c in config.get("clients", []):
            if c["handle"] == handle:
                return {
                    "handle": c["handle"],
                    "port": c["port"],
                    "whoisport": d["whoisport"],
                    "autoreply": d["autoreply"],
                    "imagepath": d["imagepath"]
                }
    return d

def update_config_field(key: str, value):
    """
    @brief Aktualisiert einen defaults-Eintrag.
    @param key Schlüsselname.
    @param value Neuer Wert.
    """
    config = load_full_config()
    config.setdefault("defaults", {})[key] = value
    save_full_config(config)

def get_config_value(key: str):
    """
    @brief Holt Wert aus defaults.
    @param key Konfig-Schlüssel.
    @return Entsprechender Wert oder None.
    """
    return load_full_config()["defaults"].get(key)

