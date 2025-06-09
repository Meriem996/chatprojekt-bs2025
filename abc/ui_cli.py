"""
@file ui_cli.py
@brief Kommandozeilen-Benutzeroberfläche für den BSRN-Chat (Netzwerk- oder Lokalbetrieb).

@details
Dieses Modul implementiert zwei Varianten der Benutzeroberfläche:
- run_cli(): für echten Netzwerkbetrieb mit SLCP und Discovery

Beide Varianten unterstützen Text- und Bildnachrichten, Konfiguration, WHOIS und Autoreply.
"""
#
import threading
import time
import os

from utils.config import update_config_field
from utils.image_tools import read_image_bytes, get_image_size, open_image
from utils.slcp import build_message

def run_cli(queue_to_net, queue_from_net, queue_to_disc, queue_from_disc, config):
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
    print(f"Willkommen im BSRN-Chat, {config['handle']}!")
    print("Verfügbare Befehle: join, leave, msg, img, whois, autoreply, config, exit\n")

    # === Eingehende Nachrichten parallel anzeigen ===
    peers = {}  # Lokale Peer-Liste für CLI

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

                # IAM-Antworten vom Discoveryprozess
                if not queue_from_disc.empty():
                    iam = queue_from_disc.get_nowait()
                    handle = iam['handle']
                    ip = iam['ip']
                    port = iam['port']
                    peers[handle] = (ip, port)  # Peer speichern!
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
            elif cmd == "leave":
                msg = build_message("LEAVE", config["handle"])
                queue_to_net.put({"type": "broadcast", "data": msg})

            # MSG – Textnachricht an anderen Benutzer
            elif cmd == "msg":
                if len(tokens) < 3:
                   print("Syntax: msg <Empfänger> <Nachricht>")
                   continue
                to = tokens[1]
                text = " ".join(tokens[2:])
                msg = build_message("MSG", config["handle"], text)   # handle = Absender
                queue_to_net.put({"type": "direct_text", "to": to, "data": msg})

            # IMG – Bild versenden
            elif cmd == "img":
                if len(tokens) != 3:
                    print("Syntax: img <Empfänger> <Bildpfad>")
                    continue
                to = tokens[1]
                path = tokens[2]
                if not os.path.exists(path):
                    print("Bildpfad existiert nicht.")
                    continue
                data = read_image_bytes(path)
                size = get_image_size(path)
                msg = build_message("IMG", to, size)
                queue_to_net.put({"type": "direct_image", "to": to, "data": msg, "binary": data})

            # WHOIS – Suche nach Benutzer im Netzwerk
            elif cmd == "whois":
                if len(tokens) != 2:
                    print("Syntax: whois <Benutzername>")
                    continue
                target = tokens[1]
                msg = build_message("WHOIS", target)
                queue_to_disc.put({"data": msg})

            # AUTOREPLY – automatische Antwort setzen
            elif cmd == "autoreply":
                if len(tokens) < 2:
                    print("Syntax: autoreply <Text>")
                    continue
                text = " ".join(tokens[1:])
                update_config_field("autoreply", text)
                print(f"Autoreply gesetzt auf: {text}")

            # CONFIG – Zeige aktuelle Konfiguration
            elif cmd == "config":
                print("Aktuelle Konfiguration:")
                for key, val in config.items():
                    print(f"  {key}: {val}")

            # EXIT – Beenden des Programms
            elif cmd == "exit":
                print("Beende Chat...")
                msg = build_message("LEAVE", config["handle"])
                queue_to_net.put({"type": "broadcast", "data": msg})
                break

            else:
                print("Unbekannter Befehl.")

        except KeyboardInterrupt:
            print("\n[INTERRUPT] Beende Chat...")
            break
        except Exception as e:
            print(f"[Fehler] {e}")