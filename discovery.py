"""
@file discovery.py
@brief Discovery-Prozess: verarbeitet WHOIS-Broadcasts und antwortet mit IAM (SLCP).

@details
Der Discovery-Prozess dient der automatischen Teilnehmererkennung im lokalen Netzwerk.
Er lauscht auf WHOIS-Nachrichten und antwortet mit IAM, wenn der lokale Benutzername
(Handle) abgefragt wird. Zusätzlich können WHOIS-Anfragen über IPC von der UI gesendet werden.
Zwei Threads arbeiten parallel:
- receive_whois(): reagiert auf eingehende WHOIS
- process_outgoing(): sendet eigene WHOIS-Anfragen ins Netzwerk
"""

import socket
import threading
import time

from utils.config import load_config
from utils.slcp import parse_message, build_message


def run_discovery(queue_from_ui, queue_to_ui_net):
    """
    @brief Startet den Discoveryprozess zur Netzwerkerkennung von Peers.

    @details Initialisiert einen UDP-Socket, um:
    - eingehende WHOIS-Nachrichten zu verarbeiten (und bei Bedarf IAM zu senden)
    - IAM-Antworten anderer Clients an die UI weiterzugeben
    - WHOIS-Nachrichten, die vom Benutzer kommen, zu broadcasten

    @param queue_from_ui WHOIS-Anfragen aus der CLI/GUI
    @param queue_to_ui IAM-Antworten für die UI
    """

    # Konfigurationsdaten laden
    config = load_config()
    whois_port = config["whoisport"]
    local_handle = config["handle"]
    local_port = config["port"]

    # === UDP-Socket einrichten für Broadcast-Empfang und -Versand ===
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.bind(("", whois_port))  # lauscht auf allen verfügbaren Netzwerkschnittstellen

    print(f"[Discovery] Listening for WHOIS on UDP-Port {whois_port}")

    def receive_whois():
        """
        @brief Thread zum Empfang und zur Verarbeitung eingehender WHOIS- oder IAM-Nachrichten.
        @details
        - Prüft, ob eine WHOIS-Anfrage dem eigenen Handle entspricht → antwortet mit IAM
        - Erkennt eingehende IAM-Nachrichten und leitet sie zur Anzeige an die UI weiter
        """
        while True:
            try:
                # WHOIS/IAM-Nachricht empfangen
                data, addr = udp_socket.recvfrom(1024)
                message = data.decode("utf-8").strip()
                parsed = parse_message(message)

                # === WHOIS erhalten → prüfen, ob es an uns gerichtet ist ===
                if parsed["command"] == "WHOIS" and parsed["params"][0] == local_handle:
                    try:
                        target_port = int(parsed["params"][1])  # ← der Port des Fragenden
                    except (IndexError, ValueError):
                        print("[Discovery-Fehler] WHOIS enthält keinen gültigen Ziel-Port")
                        continue

                    iam_msg = build_message("IAM", local_handle, get_own_ip(), local_port)
                    print(f"[Discovery] IAM wird gesendet an {(addr[0], target_port)}")
                    udp_socket.sendto(iam_msg.encode("utf-8"), (addr[0], target_port))
                    print(f"[Discovery] WHOIS erhalten von {addr}, IAM gesendet")

                # === IAM erhalten → weiterleiten an UI ===
                elif parsed["command"] == "IAM":
                    handle, ip, port = parsed["params"]

                    queue_to_ui_net.put({
                        "type": "iam",
                        "handle": handle,
                        "ip": ip,
                        "port": int(port)
                    })


            except Exception as e:
                print(f"[Discovery-Fehler] {e}")
            time.sleep(0.1)  # CPU-Last reduzieren

    def process_outgoing():
