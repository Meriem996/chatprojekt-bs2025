"""
@file network.py
@brief Netzwerkprozess für das BSRN-Chatprogramm
@details
Dieser Prozess ist für die Verarbeitung aller netzwerkbezogenen Aufgaben 
innerhalb des Chatprogramms verantwortlich. Er:
- lauscht auf SLCP-Kommandos (JOIN, LEAVE, MSG, IMG, IAM, WHOIS) via UDP,
- empfängt Bilder und lange Texte über TCP,
- sendet Nachrichten an andere Clients via UDP/TCP,
- verwaltet die Peer-Datenbank (Handles, IPs, Ports, Online-Status),
- kommuniziert mit der Benutzeroberfläche (UI) und dem Discoveryprozess über IPC-Queues.
"""

import socket, threading, time
from utils.config import get_config_value
from utils.slcp import build_message, parse_message
from utils.image_tools import save_image

peers, peer_status = {}, {}
joined = False

def get_broadcast_address():
    """
    @brief Ermittelt die Broadcast-Adresse für das lokale Subnetz.
    @details Wandelt z. B. 192.168.0.12 → 192.168.0.255 um.
    @return Broadcast-Adresse als String
    """
    try:
        ip = socket.gethostbyname(socket.gethostname()).split('.')
        return f"{ip[0]}.{ip[1]}.{ip[2]}.255"
    except: return "255.255.255.255"

def run_network(queue_from_ui, queue_to_ui, queue_from_discovery, config):
    """
    @brief Startet den Netzwerkprozess und initialisiert alle Netzwerk-Komponenten.
    @param queue_from_ui Queue mit Nachrichten von der UI (JOIN, MSG, IMG etc.)
    @param queue_to_ui Queue für Nachrichten an die UI (Textnachrichten, Bilder, Status)
    @param queue_from_discovery Queue mit IAM-Antworten vom Discoveryprozess
    @param config Konfigurationsdaten des lokalen Benutzers (Handle, Port etc.)
    """
    handle, listen_port, image_dir, whois_port = config["handle"], config["port"], config["imagepath"], config["whoisport"]

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.bind(("", listen_port))

    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp.bind(("", listen_port))
    tcp.listen(10)

    def receive_udp():
        """
        @brief Thread: Empfang und Verarbeitung eingehender SLCP-Nachrichten über UDP.
        @details
        Erkennt JOIN, LEAVE, MSG, WHOIS und IAM. 
        Behandelt Autoreply, Peer-Registrierung und leitet Inhalte ggf. an die UI weiter.
        """
        while True:
            try:
                data, addr = udp.recvfrom(1024)
                cmd, params = (p := parse_message(data.decode()))["command"], p["params"]

                if cmd == "JOIN":
                    peers[params[0]], peer_status[params[0]] = (addr[0], int(params[1])), True
                    print(f"[JOIN] {params[0]} online @ {addr[0]}:{params[1]}")

                elif cmd == "LEAVE" and params[0] in peers:
                    peer_status[params[0]] = False
                    print(f"[LEAVE] {params[0]} hat den Chat verlassen.")

                elif cmd == "MSG":
                    sender, text = params[0], params[1]
                    if not joined and sender != handle and (reply := get_config_value("autoreply")):
                        send_udp(sender, build_message("MSG", handle, f"[autoreply] {reply}"), True)
                        return
                    queue_to_ui.put({"type": "text", "from": sender, "text": text, "is_self": False})

                elif cmd == "WHOIS":
                    peers[params[0]] = (addr[0], int(params[1]))
                    if not joined and (reply := get_config_value("autoreply")) and params[0] != handle:
                        send_udp(params[0], build_message("MSG", handle, reply), True)

                elif cmd == "IAM":
                    peers[params[0]] = (params[1], int(params[2]))
                    print(f"[IAM] {params[0]} @ {params[1]}:{params[2]}")

            except Exception as e:
                print(f"[UDP-Fehler] {e}")
            time.sleep(0.1)

    def tcp_listener():
        """
        @brief Thread: Hört auf TCP-Verbindungen zum Empfang von Bildern und langen Nachrichten.
        """
        while True:
            try:
                threading.Thread(target=handle_tcp, args=(tcp.accept()[0],), daemon=True).start()
            except: continue

    def handle_tcp(conn):
        """
        @brief Verarbeitet eingehende TCP-Kommunikation.
        @details 
        Erkennt SLCP-Kommandos (MSG/IMG), speichert empfangene Bilddaten und
        leitet Inhalte an die UI-Queue weiter.
        """
        try:
            cmd, params = (p := parse_message(conn.recv(512).decode()))["command"], p["params"]
            if cmd == "MSG":
                queue_to_ui.put({"type": "text", "from": params[0], "text": params[1]})
            elif cmd == "IMG":
                size, comment = (c := params[1].split('|', 1)) if '|' in params[1] else (params[1], "")
                size, data = int(size), b""
                while len(data) < size: data += conn.recv(size - len(data))
                queue_to_ui.put({"type": "image", "from": params[0], "path": save_image(data, image_dir, params[0]), "comment": comment.strip()})
        except Exception as e:
            print(f"[TCP-Fehler] {e}")
        finally: conn.close()

    def ui_input_handler():
        """
        @brief Thread: Verarbeitet Befehle von der UI (JOIN, MSG, IMG etc.).
        @details
        Unterscheidet zwischen Broadcast (JOIN/LEAVE), Direktnachricht (MSG) 
        und Bildversand (IMG). Sendet je nach Typ über UDP oder TCP.
        """
        global joined
        while True:
            try:
                if queue_from_ui.empty(): continue
                item = queue_from_ui.get_nowait()
                if item["type"] == "broadcast":
                    parsed = parse_message(item["data"])
                    joined = parsed["command"] == "JOIN" if parsed["command"] in ("JOIN", "LEAVE") else joined
                    udp.sendto(item["data"].encode(), (get_broadcast_address(), whois_port))
                elif item["type"] == "direct_text": send_udp(item["to"], item["data"])
                elif item["type"] == "direct_image": send_tcp(item["to"], item["binary"], item.get("comment", ""))
            except Exception as e:
                print(f"[UI→Netzwerk Fehler] {e}")
            time.sleep(0.1)

    def discovery_input_handler():
        """
        @brief Thread: Verarbeitet IAM-Nachrichten aus dem Discoveryprozess.
        @details Speichert erkannte Peers in die lokale Peer-Datenbank.
        """
        while True:
            try:
                if not queue_from_discovery.empty():
                    item = queue_from_discovery.get_nowait()
                    if item["type"] == "iam":
                        peers[item["handle"]] = (item["ip"], item["port"])
                        print(f"[IAM via Discovery] {item['handle']} @ {item['ip']}:{item['port']}")
            except Exception as e:
                print(f"[IAM-Queue-Fehler] {e}")
            time.sleep(0.1)

    def send_udp(to, msg, allow_if_offline=False):
        """
        @brief Sendet SLCP-Kommandos direkt per UDP an einen Peer.
        @param to Ziel-Handle
        @param msg SLCP-Nachricht als Text
        @param allow_if_offline Optional: auch senden, wenn nicht gejoined
        """
        if not joined and not allow_if_offline: return print("[ABGELEHNT] Nicht gejoint.")
        if to not in peers: return print(f"[Fehler] Peer {to} nicht bekannt")
        try: udp.sendto(msg.encode(), peers[to])
        except Exception as e: print(f"[UDP-Sendeproblem] {e}")

    def send_tcp(to, data, comment=""):
        """
        @brief Sendet Binärdaten (z. B. Bilder) per TCP an einen Peer.
        @param to Ziel-Handle
        @param data Bilddaten als Bytes
        @param comment Optionaler Bildkommentar
        """
        if not joined: return print("[ABGELEHNT] Nicht gejoint.")
        if to not in peers: return print(f"[Fehler] Peer {to} fehlt")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(peers[to])
            s.sendall(build_message("IMG", handle, f"{len(data)}|{comment}").encode())
            time.sleep(0.05)
            s.sendall(data)
            s.close()
        except Exception as e: print(f"[TCP-Sendeproblem] {e}")

    # Threads starten
    for fn in [receive_udp, tcp_listener, ui_input_handler, discovery_input_handler]:
        threading.Thread(target=fn, daemon=True).start()

    while True: time.sleep(1)