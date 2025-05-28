"""
@file main.py
@brief Startpunkt für das BSRN-Chatprogramm.
@details
Dieses Modul startet das gesamte Chatprogramm.
Es bietet die Auswahl zwischen:
- Netzwerkmodus: Kommunikation über SLCP mit Discovery, Netzwerk und GUI/CLI
- Lokalem Modus: Zwei Benutzer auf demselben Gerät (z. B. GUI ↔ CLI über UDP oder Queue)

Alle Prozesse werden sauber getrennt über multiprocessing gestartet.
"""

import multiprocessing
import sys
import time
import subprocess
import os

# Import der globalen IPC-Queues
from ipc import (
    queue_ui_to_net,
    queue_net_to_ui,
    queue_ui_to_discovery,
    queue_discovery_to_ui,
    queue_discovery_to_net
)

# Konfiguration laden/speichern
from utils.config import update_config_field, load_config

# Hauptprozesse
import ui_cli
import ui_gui
import network
import discovery


def choose_mode():
    """
    @brief Fragt den gewünschten Betriebsmodus ab (Netzwerk oder lokal).
    @return "1" für Netzwerkmodus, "2" für lokalen Modusa
    """
    while True:
        print("Wähle den Modus:")
        print("1 – Netzwerkmodus (Chat über Netzwerk)")
        print("2 – Lokaler Modus (zwei Fenster auf diesem Gerät)")
        choice = input("Modus wählen (1/2): ").strip()
        if choice in ("1", "2"):
            return choice


def choose_ui():
    """
    @brief Fragt die Benutzeroberfläche ab (CLI oder GUI).
    @return "cli" oder "gui"
    """
    while True:
        choice = input("Welche Benutzeroberfläche willst du starten? [cli/gui]: ").strip().lower()
        if choice in ("cli", "gui"):
            return choice
        print("Ungültige Eingabe. Bitte 'cli' oder 'gui' eingeben.")


def choose_ui_local(role):
    """
        @brief Im lokalen Modus: Oberfläche für Benutzer 1 oder 2 wählen.
        @param role "Benutzer 1" oder "Benutzer 2"
        @return "cli" oder "gui"
        """
    while True:
        choice = input(f"Wähle Oberfläche für {role} [cli/gui]: ").strip().lower()
        if choice in ("cli", "gui"):
            return choice
        print("Ungültige Eingabe. Bitte 'cli' oder 'gui' eingeben.")


def ask_name_cli():
    """
    @brief Liest den Namen des Benutzers für CLI aus und speichert ihn in der Konfiguration.
    """
    while True:
        name = input("Wie heißt du? ").strip()
        if name:
            update_config_field("handle", name)
            return
        print("Name darf nicht leer sein.")


def main():
    """
    @brief Zentrale Steuerfunktion des Chatprogramms.
    @details Je nach Moduswahl wird entweder der Netzwerk- oder der lokale Modus gestartet.
    Die Prozesse für GUI, Netzwerk und Discovery laufen dabei separat (außer CLI).
    """

    print("== BSRN-Chatprogramm Initialisierung ==")

    mode = choose_mode()

    if mode == "1":
        # === Netzwerkmodus ===
        ui_mode = choose_ui()

        if ui_mode == "cli":
            ask_name_cli()

        try:
            config = load_config()
            print(f"[OK] Konfiguration geladen für Benutzer: {config['handle']}")
        except Exception as e:
            print(f"[Fehler] Konfigurationsfehler: {e}")
            sys.exit(1)

        processes = []

        if ui_mode == "cli":

            try:
                config = load_config()
                print(f"[OK] Konfiguration geladen für Benutzer: {config['handle']}")
            except Exception as e:
                print(f"[Fehler] Konfigurationsfehler: {e}")
                sys.exit(1)

            # Starte Netzwerkprozess
            p_net = multiprocessing.Process(
                target=network.run_network,
                args=(queue_ui_to_net, queue_net_to_ui, queue_discovery_to_net),
                name="Netzwerk-Prozess"
            )

            # Starte Discoveryprozess
            p_disc = multiprocessing.Process(
                target=discovery.run_discovery,
                args=(queue_ui_to_discovery, queue_discovery_to_net),
                name="Discovery-Prozess"
            )

            p_net.start()
            p_disc.start()
            print(f"[INFO] Prozess gestartet: {p_net.name} (PID: {p_net.pid})")
            print(f"[INFO] Prozess gestartet: {p_disc.name} (PID: {p_disc.pid})")

            # CLI läuft im Hauptprozess
            ui_cli.run_cli(queue_ui_to_net, queue_net_to_ui, queue_ui_to_discovery, queue_discovery_to_ui)

            # Wenn CLI beendet wurde, Prozesse beenden
            p_net.terminate()
            p_disc.terminate()
            p_net.join()
            p_disc.join()
            print("[INFO] Prozesse nach CLI-Ende sauber beendet.")

            return

        else:
            # GUI-Prozess separat starten
            p_ui = multiprocessing.Process(
                target=ui_gui.run_gui,
                args=(queue_ui_to_net, queue_net_to_ui, queue_ui_to_discovery, queue_discovery_to_ui),
                name="GUI-Prozess"
            )
            processes.append(p_ui)

            # Netzwerkprozess: empfängt/versendet SLCP-Befehle
        p_net = multiprocessing.Process(
            target=network.run_network,
            args=(queue_ui_to_net, queue_net_to_ui, queue_discovery_to_net),  # ⬅ NEU
            name="Netzwerk-Prozess"
        )
        processes.append(p_net)

        # Discoveryprozess: WHOIS/IAM-Verarbeitung
        p_disc = multiprocessing.Process(
            target=discovery.run_discovery,
            args=(queue_ui_to_discovery, queue_discovery_to_net),  # ⬅ Discovery sendet direkt an Network!
            name="Discovery-Prozess"
        )
        processes.append(p_disc)

        # Prozesse starten
        for p in processes:
            p.start()
            print(f"[INFO] Prozess gestartet: {p.name} (PID: {p.pid})")

        try:
            for p in processes:
                p.join()
        except KeyboardInterrupt:
            print("\n[INFO] Abbruch erkannt. Prozesse werden beendet...")
            for p in processes:
                p.terminate()
                p.join()
            print("[INFO] Alle Prozesse sauber beendet.")