"""
@file main.py
@brief Startpunkt für das BSRN-Chatprogramm.
@details
Dieses Modul startet das gesamte Chatprogramm im Netzwerkmodus (CLI).
Die Prozesse für Netzwerk und Discovery laufen separat.
"""

import multiprocessing
import sys
import os

# Import der globalen IPC-Queues
from ipc import (
    queue_ui_to_net,
    queue_net_to_ui,
    queue_ui_to_discovery,
    queue_discovery_to_ui,
    queue_discovery_to_net
)

DISCOVERY_LOCK = "/tmp/bsrn_discovery.lock"  

# Konfiguration laden/speichern
from utils.config import get_or_create_client_config

# Hauptprozesse
import ui_cli
import network
import discovery
import socket 



config = None
p_disc = None

def is_discovery_running_by_lock():
    if not os.path.exists(DISCOVERY_LOCK):
        return False

    try:
        with open(DISCOVERY_LOCK, "r") as f:
            pid = int(f.read().strip())
        # Prüfen, ob Prozess mit dieser PID noch lebt
        os.kill(pid, 0)
        return True  # Prozess existiert → Lock ist gültig
    except (ValueError, ProcessLookupError, PermissionError):
        # Prozess existiert nicht → Lock ist veraltet
        unmark_discovery()
        return False

def mark_discovery_running():
    with open(DISCOVERY_LOCK, "w") as f:
        f.write(str(os.getpid())) 

def unmark_discovery():
    if os.path.exists(DISCOVERY_LOCK):
        os.remove(DISCOVERY_LOCK)

def start_discovery_process():
    global p_disc

    if is_discovery_running_by_lock():
        print("[INFO] Discovery-Prozess läuft bereits. Lokaler Empfänger wird gestartet.")
        p_disc = multiprocessing.Process(
            target=discovery.run_discovery,
            args=(queue_ui_to_discovery, queue_discovery_to_net, config),
            name="Discovery-Receiver"
        )
        p_disc.start()
        return

    # Voller Prozess, nur wenn noch keiner läuft
    if p_disc is None or not p_disc.is_alive():
        p_disc = multiprocessing.Process(
            target=discovery.run_discovery,
            args=(queue_ui_to_discovery, queue_discovery_to_net, config),
            name="Discovery-Prozess"
        )
        p_disc.start()
        mark_discovery_running()
        print(f"[INFO] Discovery-Prozess gestartet (PID: {p_disc.pid})")

def main():
    """
    @brief Zentrale Steuerfunktion des Chatprogramms im CLI-Modus.
    @details Startet Netzwerk- und Discoveryprozess und führt CLI im Hauptprozess aus.
    """

    global config

    print("== BSRN-Chatprogramm Initialisierung (CLI-Modus) ==")

    # Benutzername abfragen
    print("Bitte gib deinen Namen (Handle) ein:")
    handle = input("> ").strip()
    if not handle:
        print("[Fehler] Handle darf nicht leer sein.")
        sys.exit(1)

    try:
        config = get_or_create_client_config(handle)
        print(f"[OK] Konfiguration geladen oder erstellt für Benutzer: {config['handle']} (Port {config['port']})")
    except Exception as e:
        print(f"[Fehler] Konfigurationsfehler: {e}")
        sys.exit(1)

    # Netzwerkprozess starten
    p_net = multiprocessing.Process(
        target=network.run_network,
        args=(queue_ui_to_net, queue_net_to_ui, queue_discovery_to_net, config),
        name="Netzwerk-Prozess"
    )

    p_net.start()

    print(f"[INFO] Prozess gestartet: {p_net.name} (PID: {p_net.pid})")
    if p_disc is not None:
       print(f"[INFO] Prozess gestartet: {p_disc.name} (PID: {p_disc.pid})")

    ui_cli.run_cli(queue_ui_to_net, queue_net_to_ui, queue_ui_to_discovery, queue_discovery_to_ui, config, lambda: start_discovery_process())

    # Prozesse beenden, sobald CLI endet
    p_net.terminate()
    p_net.join()
    if p_disc is not None:
       p_disc.terminate()
       p_disc.join()
       unmark_discovery()

    print("[INFO] Prozesse nach CLI-Ende sauber beendet.")

# === Einstiegspunkt ===
if __name__ == "__main__":
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass

    main()
