"""
Zentrale Konfigurationsverwaltung für das Chatprojekt.
Lädt und speichert config.toml, verwaltet Clients und Ports.
"""

import os, toml, socket
from threading import Lock
from pathlib import Path

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.toml'))
_lock = Lock()

def load_full_config() -> dict:
    """Lädt komplette TOML-Konfiguration."""
    with _lock:
        if not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError(f"Datei fehlt: {CONFIG_PATH}")
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return toml.load(f)

def save_full_config(config: dict):
    """Speichert gesamte Konfiguration."""
    with _lock:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            toml.dump(config, f)

def is_port_available(port: int) -> bool:
    """Gibt True zurück, wenn der Port nicht belegt ist."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0

def find_free_port(config: dict) -> int:
    """Sucht freien Port im Bereich defaults.port_range."""
    prange = config["defaults"].get("port_range", [5000, 5100])
    used = [c["port"] for c in config.get("clients", [])]
    for p in range(prange[0], prange[1]+1):
        if p not in used and is_port_available(p):
            return p
    raise RuntimeError("Kein freier Port verfügbar")

def get_or_create_client_config(handle: str) -> dict:
    """Lädt oder erstellt Konfig für gegebenes Handle."""
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
        "imagepath": d["imagepath"],
        "dark_mode": d.get("dark_mode", False)
    }

def load_config(handle: str = None) -> dict:
    """Lädt Konfiguration für Handle (falls angegeben) oder nur defaults."""
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
                    "imagepath": d["imagepath"],
                    "dark_mode": d.get("dark_mode", False)
                }
    return d

def update_config_field(key: str, value):
    """Ändert ein defaults-Feld und speichert."""
    config = load_full_config()
    config.setdefault("defaults", {})[key] = value
    save_full_config(config)

def get_config_value(key: str):
    """Liest ein Feld aus defaults."""
    return load_full_config()["defaults"].get(key)
