"""
@file main.py
@brief Startpunkt für das BSRN-Chatprogramm.
@details
Dieses Modul startet das gesamte Chatprogramm im Netzwerkmodus (CLI).
Die Prozesse für Netzwerk und Discovery laufen separat.
"""

import multiprocessing
import sys

# Import der globalen IPC-Queues
from ipc import (
    queue_ui_to_net,
    queue_net_to_ui,
    queue_ui_to_discovery,
    queue_discovery_to_ui,
    queue_discovery_to_net
)

# Konfiguration laden/speichern
from utils.config import get_or_create_client_config

# Hauptprozesse
import ui_cli
import network
import discovery

def main():
    """
    @brief Zentrale Steuerfunktion des Chatprogramms im CLI-Modus.
    @details Startet Netzwerk- und Discoveryprozess und führt CLI im Hauptprozess aus.
    """

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

    # Discoveryprozess starten
    p_disc = multiprocessing.Process(
        target=discovery.run_discovery,
        args=(queue_ui_to_discovery, queue_discovery_to_net, config),
        name="Discovery-Prozess"
    )

    p_net.start()
    p_disc.start()
    print(f"[INFO] Prozess gestartet: {p_net.name} (PID: {p_net.pid})")
    print(f"[INFO] Prozess gestartet: {p_disc.name} (PID: {p_disc.pid})")

    # CLI im Hauptprozess ausführen
    ui_cli.run_cli(queue_ui_to_net, queue_net_to_ui, queue_ui_to_discovery, queue_discovery_to_ui, config)

    # Prozesse beenden, sobald CLI endet
    p_net.terminate()
    p_disc.terminate()
    p_net.join()
    p_disc.join()
    print("[INFO] Prozesse nach CLI-Ende sauber beendet.")

# === Einstiegspunkt ===
if __name__ == "__main__":
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass

    main()