"""
@file network.py
@brief Netzwerkprozess: verarbeitet SLCP-Nachrichten, versendet/empfängt MSG & IMG, verwaltet Kontakte.

@details
Dieser Prozess ist einer der drei Hauptprozesse des BSRN-Chatprogramms.
Er verarbeitet alle Netzwerkaktionen über das Simple Local Chat Protocol (SLCP).
Er:
- lauscht auf UDP (JOIN, LEAVE, MSG, IMG-Steuerbefehl)
- empfängt Daten über TCP (Bilder und lange Nachrichten)
- sendet Nachrichten direkt per UDP/TCP
- pflegt eine Liste aller bekannten Teilnehmer ("peers")
- leitet Nachrichten und Updates an die UI weiter
"""

import socket
import threading
import time

from utils.config import get_config_value
from utils.slcp import build_message, parse_message
from utils.image_tools import save_image

# Lokale Peer-Datenbank: handle → (IP, Port)
# Wird durch JOIN, WHOIS/IAM oder eingehende Nachrichten gepflegt
peers = {}


def get_broadcast_address():
    """
    @brief Ermittelt die passende Broadcast-Adresse für das lokale Subnetz.
    @details Wandelt z. B. 192.168.1.24 → 192.168.1.255 um.
             Fallback: 255.255.255.255 bei Fehlern.
    @return Broadcast-IP als String
    """
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        base = '.'.join(ip.split('.')[:-1])
        return f"{base}.255"
    except Exception:
        return '255.255.255.255'


def run_network(queue_from_ui, queue_to_ui, queue_from_discovery, config):
    """
    @brief Startet den Netzwerkprozess: SLCP-Verarbeitung, TCP/UDP-Kommunikation und Peer-Verwaltung.
    @param queue_from_ui Nachrichten von der UI (z. B. MSG, IMG, JOIN etc.)
    @param queue_to_ui Nachrichten an die UI (empfangene Texte, Bilder, Peer-Updates)
    Intern enthält diese Methode u. a.:
    - receive_udp(): verarbeitet eingehende SLCP-Befehle (UDP)
    - tcp_listener(): empfängt TCP-Daten (z. B. Bilder)
    - send_direct_udp(): verschickt UDP-Nachrichten an Peers
    - send_direct_tcp(): verschickt Bilddaten an Peers (TCP)
    - ui_input_handler(): verarbeitet UI-Befehle
    - discovery_input_handler(): verarbeitet IAM-Nachrichten
    """

    # Konfiguration laden
    whois_port = config["whoisport"]  # WHOIS-Port laden
    handle = config["handle"]
    listen_port = config["port"]
    image_dir = config["imagepath"]

    # === UDP-Socket vorbereiten (für SLCP-Befehle über UDP) ===
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(("", listen_port))

    # === TCP-Socket für eingehende Verbindungen (z. B. Bilder) ===
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_socket.bind(("", listen_port))
    tcp_socket.listen(10)

    print(f"[Netzwerk] Lausche auf Port {listen_port} (UDP & TCP)")

    def receive_udp():
        """
        @brief UDP-Listener: verarbeitet alle eingehenden SLCP-Nachrichten.
        @details Unterstützt JOIN, LEAVE, MSG, IMG (Steuerbefehl)
        """
        while True:
            try:
                data, addr = udp_socket.recvfrom(1024)
                message = data.decode("utf-8").strip()
                parsed = parse_message(message)
                command = parsed["command"]
                params = parsed["params"]

                if command == "JOIN":
                    sender, sender_port = params[0], int(params[1])
                    peers[sender] = (addr[0], sender_port)
                    print(f"[JOIN] {sender} @ {addr[0]}:{sender_port}")

                elif command == "LEAVE":
                    sender = params[0]
                    if sender in peers:
                        del peers[sender]
                        print(f"[LEAVE] {sender} hat den Chat verlassen.")

                elif command == "MSG":
                    sender, text = params[0], params[1]

                    queue_to_ui.put({
                        "type": "text",
                        "from": sender,
                        "text": text,
                        "is_self": False  # Nachricht stammt vom anderen Peer
                    })

                elif command == "WHOIS":
                    sender = params[0]  # z.B. "A"
                    sender_port = int(params[1])
                    peers[sender] = (addr[0], sender_port)
                    print(f"[WHOIS] erhalten von {sender} @ {addr[0]}:{sender_port}")

                    # Autoreply senden, wenn gesetzt
                    reply = get_config_value("autoreply")
                    if sender != handle and reply:
                       auto_msg = build_message("MSG", handle, reply)
                       send_direct_udp(sender, auto_msg)

                elif command == "IAM":
                    sender, ip, port = params[0], params[1], int(params[2])
                    peers[sender] = (ip, port)
                    print(f"[IAM] {sender} @ {ip}:{port} erkannt")

                elif command == "IMG":
                    # Nur Header – Bilddaten folgen per TCP
                    pass

            except Exception as e:
                print(f"[UDP-Fehler] {e}")
            time.sleep(0.1)

    def tcp_listener():
        """
        @brief TCP-Listener: akzeptiert eingehende Verbindungen (für MSG oder IMG).
        """
        while True:
            try:
                conn, addr = tcp_socket.accept()
                threading.Thread(target=handle_tcp_client, args=(conn,), daemon=True).start()
            except Exception:
                continue

    def handle_tcp_client(conn):
        """
        @brief Behandelt eingehende TCP-Verbindungen.
        @param conn Offene TCP-Verbindung
        @details Erkennt SLCP-Kommando, empfängt Bilddaten und sendet sie an die UI.
        """