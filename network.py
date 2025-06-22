## @file network.py
## @brief Netzwerkprozess für SLCP-Kommunikation und Peer-Verwaltung
##
## @details
## Dieser Prozess übernimmt die komplette Netzwerkkommunikation im BSRN-Chat:
## - empfängt Nachrichten über UDP (JOIN, LEAVE, MSG)
## - sendet Textnachrichten per UDP
## - empfängt und sendet Bildnachrichten per TCP
## - verarbeitet IAM-Nachrichten zur Peer-Erkennung

import socket, threading, time
from utils.slcp import build_message, parse_message
from utils.config import get_config_value
from utils.image_tools import save_image
from utils.network_utils import detect_broadcast_address

peers, peer_status = {}, {}
joined = False

def run_network(queue_ui_in, queue_ui_out, queue_disc_in, config):
    ## @brief Startet alle Netzwerk-Komponenten
    ## @param queue_ui_in Eingehende Nachrichten von der UI (JOIN, MSG, IMG etc.)
    ## @param queue_ui_out Nachrichten an die UI (Text/Bildnachrichten)
    ## @param queue_disc_in IAM-Nachrichten vom Discovery-Modul
    ## @param config Konfigurationswerte wie Port, Handle, Bildpfad

    port, handle = config["port"], config["handle"]

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp.bind(("", port))

    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp.bind(("", port))
    tcp.listen(10)

    def receive_udp():
        ## @brief Verarbeitet alle eingehenden SLCP-Nachrichten über UDP
        ## @details Erkennt JOIN, LEAVE, MSG, WHOIS, IAM
        while True:
            try:
                msg, addr = udp.recvfrom(1024)
                parsed = parse_message(msg.decode("utf-8"))
                cmd, p = parsed["command"], parsed["params"]
                
                if cmd == "JOIN":
                    peers[p[0]] = (addr[0], int(p[1]))
                    peer_status[p[0]] = True
                elif cmd == "LEAVE":
                    peer_status[p[0]] = False
                elif cmd == "MSG" and joined:
                    queue_ui_out.put({"type": "text", "from": p[0], "text": p[1], "is_self": False})
                elif cmd == "MSG":
                    if (reply := get_config_value("autoreply")) and p[0] != handle:
                        m = build_message("MSG", handle, "[autoreply] " + reply)
                        send_udp(p[0], m, True)
                elif cmd == "WHOIS":
                    peers[p[0]] = (addr[0], int(p[1]))
                elif cmd == "IAM":
                    peers[p[0]] = (p[1], int(p[2]))
            except: pass
            time.sleep(0.1)

    def tcp_listener():
        ## @brief Lauscht auf eingehende TCP-Verbindungen (z. B. für Bildtransfer)
        while True:
            try:
                conn, _ = tcp.accept()
                threading.Thread(target=handle_tcp, args=(conn,), daemon=True).start()
            except: continue

    def handle_tcp(conn):
        ## @brief Verarbeitet eine einzelne TCP-Verbindung
        ## @details Empfängt Header + Daten (IMG oder MSG) und sendet an die UI weiter
        try:
            header = conn.recv(512).decode().strip()
            parsed = parse_message(header)
            if parsed["command"] == "IMG":
                sender, info = parsed["params"]
                size, comment = (info + "|").split("|", 1)[:2]
                img = b""
                while len(img) < int(size): img += conn.recv(1024)
                path = save_image(img, config["imagepath"], sender)
                queue_ui_out.put({"type": "image", "from": sender, "path": path, "comment": comment.strip()})
            elif parsed["command"] == "MSG":
                queue_ui_out.put({"type": "text", "from": parsed["params"][0], "text": parsed["params"][1]})
        except: pass
        finally: conn.close()

    def handle_ui():
        ## @brief Verarbeitet SLCP-Befehle, die von der UI gesendet wurden
        ## @details Erkennt JOIN, LEAVE, MSG und IMG Befehle
        global joined
        while True:
            try:
                if queue_ui_in.empty(): continue
                item = queue_ui_in.get_nowait()
                if item["type"] == "broadcast":
                    cmd = parse_message(item["data"])["command"]
                    joined = cmd == "JOIN"
                    ip = detect_broadcast_address()
                    udp.sendto(item["data"].encode(), (ip, config["whoisport"]))
                elif item["type"] == "direct_text":
                    send_udp(item["to"], item["data"])
                elif item["type"] == "direct_image":
                    send_tcp(item["to"], item["binary"], item.get("comment", ""))
            except: pass
            time.sleep(0.1)

    def handle_discovery():
        ## @brief Verarbeitet IAM-Nachrichten, die vom Discovery-Modul kommen
        while True:
            try:
                if queue_disc_in.empty(): continue
                i = queue_disc_in.get_nowait()
                if i["type"] == "iam":
                    peers[i["handle"]] = (i["ip"], i["port"])
            except: pass
            time.sleep(0.1)

    def send_udp(to, msg, allow=False):
        ## @brief Sendet UDP-Nachricht an Peer
        ## @param to Empfänger-Handle
        ## @param msg SLCP-formatierte Nachricht
        ## @param allow Wenn True, auch senden wenn nicht "joined"
        if not joined and not allow: return
        if to in peers:
            try: udp.sendto(msg.encode(), peers[to])
            except: pass

    def send_tcp(to, data, comment=""):
        ## @brief Sendet Binärdaten (z. B. Bild) per TCP
        ## @param to Ziel-Handle
        ## @param data Binärinhalt
        ## @param comment Optionaler Textkommentar
        if not joined or to not in peers: return
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(peers[to])
            header = build_message("IMG", config["handle"], f"{len(data)}|{comment}")
            s.sendall(header.encode())
            time.sleep(0.05)
            s.sendall(data)
            s.close()
        except: pass

    threading.Thread(target=receive_udp, daemon=True).start()
    threading.Thread(target=tcp_listener, daemon=True).start()
    threading.Thread(target=handle_ui, daemon=True).start()
    threading.Thread(target=handle_discovery, daemon=True).start()
    while True: time.sleep(1)