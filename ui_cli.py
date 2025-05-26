"""
@file ui_cli.py
@brief Kommandozeilen-Benutzeroberfläche für den BSRN-Chat (Netzwerk- oder Lokalbetrieb).

@details
Dieses Modul implementiert zwei Varianten der Benutzeroberfläche:
- run_cli(): für echten Netzwerkbetrieb mit SLCP und Discovery
- run_cli_local(): für lokale Kommunikation mit GUI oder anderer CLI über IPC

Beide Varianten unterstützen Text- und Bildnachrichten, Konfiguration, WHOIS und Autoreply.
"""

import threading
import time
import os

import discovery
from utils.config import load_config, update_config_field
from utils.image_tools import read_image_bytes, get_image_size, open_image
from utils.slcp import build_message


def run_cli(queue_to_net, queue_from_net, queue_to_disc, queue_from_disc):
    """
    @brief Startet die CLI-Oberfläche des Chatprogramms im Netzwerkmodus.
    @details Lädt Konfiguration, startet Listener-Thread und verarbeitet Benutzerbefehle.

    Unterstützte Befehle:
      - join
      - leave
      - msg <Empfänger> <Nachricht>
      - img <Empfänger> <Pfad>
      - whois <Benutzername>
      - autoreply <Text>
      - config
      - exit

    @param queue_to_net Queue zur Kommunikation mit Netzwerkprozess (Senden)
    @param queue_from_net Queue zum Empfang von Nachrichten vom Netzwerkprozess
    @param queue_to_disc Queue zur Kommunikation mit Discoveryprozess (WHOIS)
    @param queue_from_disc Queue zum Empfang von IAM-Antworten
    """
    config = load_config()
    myip = discovery.get_own_ip()

    print(myip)
    print(f"Willkommen im BSRN-Chat, {config['handle']}!")
    print("Verfügbare Befehle: join, leave, msg, img, whois, autoreply, config, exit\n")

    # === Eingehende Nachrichten parallel anzeigen ===
    peers = {}  # 🔧 Lokale Peer-Liste für CLI

    def listener():
        """
        @brief Hintergrund-Thread zur asynchronen Anzeige von Nachrichten und WHOIS-Antworten.
        """
        while True:
            try:
                # Nachrichten vom Netzwerkprozess
                if not queue_from_net.empty():
                    msg = queue_from_net.get_nowait()

                    if msg["type"] == "text":
                        print(f"\n[Nachricht von {msg['from']}] {msg['text']}")
                    elif msg["type"] == "image":
                        print(f"\n[Empfangenes Bild von {msg['from']}] gespeichert: {msg['path']}")
                        open_image(msg['path'])  # optional automatisch öffnen

                # IAM-Antworten vom Discoveryprozess
                if not queue_from_disc.empty():
                    iam = queue_from_disc.get_nowait()
                    handle = iam['handle']
                    ip = iam['ip']
                    port = iam['port']
                    peers[handle] = (ip, port)  # 🔧 Peer speichern!
                    print(f"\n[WHOIS-Antwort] {handle} ist erreichbar unter {ip}:{port}")

            except Exception:
                continue
            time.sleep(0.1)

    # Thread starten
    threading.Thread(target=listener, daemon=True).start()

    # === Haupt-Eingabeschleife ===
    while True:
        try:
            user_input = input(">> ").strip()
            if not user_input:
                continue

            tokens = user_input.split()
            cmd = tokens[0].lower()

            # JOIN – Anmelden im Netzwerk
            if cmd == "join":
                msg = build_message("JOIN", config["handle"], config["port"])
                queue_to_net.put({"type": "broadcast", "data": msg})

            # LEAVE – Abmelden
