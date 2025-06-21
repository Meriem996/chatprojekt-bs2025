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
from utils.network_utils import detect_broadcast_address


# Lokale Peer-Datenbank: handle → (IP, Port)
# Wird durch JOIN, WHOIS/IAM oder eingehende Nachrichten gepflegt
peers = {}
# Status aller bekannten Peers: handle → bool (True = online, False = offline)
peer_status = {}
# Status-Flag: Ist dieser Client dem Chat beigetreten?
joined = False


def get_broadcast_address():
    """
    @brief Ermittelt die passende Broadcast-Adresse für das lokale Subnetz.
    @details Wandelt z. B. 192.168.1.24 → 192.168.1.255 um.
             Fallback: 255.255.255.255 bei Fehlern.
    @return Broadcast-IP als String
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        parts = ip.split('.')
        return f"{parts[0]}.{parts[1]}.{parts[2]}.255"
    except Exception:
        return "255.255.255.255"


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
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
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
                     peer_status[sender] = True
                     print(f"[JOIN] {sender} @ {addr[0]}:{sender_port} ist jetzt online.")
                elif command == "LEAVE":
                    sender = params[0]
                    if sender in peers:
                       peer_status[sender] = False
                       print(f"[LEAVE] {sender} hat den Chat verlassen.")

                elif command == "MSG":
                    sender, text = params[0], params[1]
                    if not joined:
                       # Auto-Reply senden
                       reply = get_config_value("autoreply")
                       if sender != handle and reply:
                          auto_msg = build_message("MSG", handle, "[autoreply] " + reply)
                          send_direct_udp(sender, auto_msg, allow_if_offline=True)
                       return  # Nicht in UI anzeigen, wenn wir offline sind

                    queue_to_ui.put({
                        "type": "text",
                        "from": sender,
                        "text": text,
                        "is_self": False  # Nachricht stammt vom anderen Peer
                    })

                elif command == "WHOIS":
                     sender = params[0]  # z.B. "Alice"
                     sender_port = int(params[1])
                     peers[sender] = (addr[0], sender_port)
                     print(f"[WHOIS] erhalten von {sender} @ {addr[0]}:{sender_port}")

                     # Auto-Reply senden, wenn wir offline sind
                     if not joined:
                        reply = get_config_value("autoreply")
                        if sender != handle and reply:
                           auto_msg = build_message("MSG", handle, reply)
                           send_direct_udp(sender, auto_msg, allow_if_offline=True)

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
        try:
            # Header lesen
            header = conn.recv(512).decode("utf-8").strip()
            parsed = parse_message(header)
            command = parsed["command"]
            params = parsed["params"]

            if command == "MSG":
                sender, text = params[0], params[1]
                queue_to_ui.put({"type": "text", "from": sender, "text": text})

            elif command == "IMG":
                sender = params[0]
                size_comment_raw = params[1]

                # Bildgröße und Kommentar trennen
                if '|' in size_comment_raw:
                    size_str, comment = size_comment_raw.split('|', 1)
                else:
                    size_str, comment = size_comment_raw, ""

                try:
                    size = int(size_str)
                except ValueError:
                    print(f"[TCP-Fehler] Ungültige Bildgröße: {size_str}")
                    return

                # Bilddaten empfangen
                image_data = b""
                while len(image_data) < size:
                    chunk = conn.recv(size - len(image_data))
                    if not chunk:
                        break
                    image_data += chunk

                img_path = save_image(image_data, image_dir, sender)

                # An UI schicken
                queue_to_ui.put({
                    "type": "image",
                    "from": sender,
                    "path": img_path,
                    "comment": comment.strip()
                })

        except Exception as e:
            print(f"[TCP-Fehler] {e}")
        finally:
            conn.close()

    def ui_input_handler():
        """
        @brief Verarbeitet SLCP-Befehle aus der Benutzeroberfläche.
        @details Erkennt drei Typen:
            - broadcast (JOIN, LEAVE)
            - direct_text (MSG)
            - direct_image (IMG)
        """
        global joined
        while True:
            try:
                if not queue_from_ui.empty():
                    item = queue_from_ui.get_nowait()
                    msg_type = item["type"]

                    if msg_type == "broadcast":
                        parsed = parse_message(item["data"])
                        if parsed["command"] == "JOIN":
                            joined = True
                            print("[Status] Du bist jetzt dem Chat beigetreten.")
                        elif parsed["command"] == "LEAVE":
                            joined = False
                            print("[Status] Du hast den Chat verlassen.")    
                        broadcast_ip = detect_broadcast_address()
                        udp_socket.sendto(item["data"].encode("utf-8"), (broadcast_ip, config["whoisport"]))

                    elif msg_type == "direct_text":
                        send_direct_udp(item["to"], item["data"])

                    elif msg_type == "direct_image":
                        to = item["to"]
                        binary = item["binary"]
                        comment = item.get("comment", "")
                        # Wir übergeben KEINEN Header mehr, sondern nur noch relevante Werte
                        send_direct_tcp(to, binary, comment)

            except Exception as e:
                print(f"[UI→Netzwerk Fehler] {e}")
            time.sleep(0.1)

    def send_direct_udp(to_handle, message, allow_if_offline=False):
        """
        @brief Sendet SLCP-Nachricht direkt per UDP an einen Peer.
        @param to_handle Handle des Empfängers
        @param message SLCP-Nachricht als String
        """
        if not joined and not allow_if_offline:
           print("[ABGELEHNT] Du bist nicht gejoint – Nachricht wird nicht gesendet.")
           return

        if to_handle not in peers:
            print(f"[Fehler] Kein Peer-Eintrag für '{to_handle}' vorhanden.")
            print(f"[DEBUG] Aktuelle Peers: {list(peers.keys())}")
            return

        ip, port = peers[to_handle]
        try:
            udp_socket.sendto(message.encode("utf-8"), (ip, port))
        except Exception as e:
            print(f"[UDP-Sendeproblem] {e}")

    def send_direct_tcp(to_handle, binary_data, comment=""):
        """
        @brief Sendet Nachricht inkl. Binärdaten (z. B. Bilder) per TCP an einen Peer.
        @param to_handle Ziel-Handle
        @param _ Ignorierter Parameter (früher: header_message)
        @param binary_data Binärdaten des Bildes
        @param comment Optionaler Kommentartext
        """
        if not joined:
           print("[ABGELEHNT] Du bist nicht gejoint – Bild wird nicht gesendet.")
           return

        if to_handle not in peers:
            print(f"[Fehler] Kein Eintrag für {to_handle}")
            return

        ip, port = peers[to_handle]
        try:
            handle = config["handle"]
            size = len(binary_data)

            # Header mit Kommentar in der Form: IMG <from> <size>|<comment>
            header_message = build_message("IMG", handle, f"{size}|{comment}")

            # TCP-Verbindung und Senden
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((ip, port))
            s.sendall(header_message.encode("utf-8"))
            time.sleep(0.05)  # kurze Pause zwischen Header und Bilddaten
            s.sendall(binary_data)
            s.close()

        except Exception as e:
            print(f"[TCP-Sendeproblem] {e}")

    def discovery_input_handler():
        """
        @brief Verarbeitet IAM-Nachrichten aus dem Discovery-Prozess.
        """
        while True:
            try:
                if not queue_from_discovery.empty():
                    item = queue_from_discovery.get_nowait()
                    if item["type"] == "iam":
                        handle = item["handle"]
                        ip = item["ip"]
                        port = item["port"]
                        peers[handle] = (ip, port)
                        print(f"[IAM via Discovery] {handle} @ {ip}:{port}")
            except Exception as e:
                print(f"[IAM-Queue-Fehler] {e}")
            time.sleep(0.1)

    # === Alle Threads starten ===
    threading.Thread(target=receive_udp, daemon=True).start()
    threading.Thread(target=tcp_listener, daemon=True).start()
    threading.Thread(target=ui_input_handler, daemon=True).start()
    threading.Thread(target=discovery_input_handler, daemon=True).start()

    # Hauptprozess läuft im Hintergrund weiter
    while True:
        time.sleep(1)
