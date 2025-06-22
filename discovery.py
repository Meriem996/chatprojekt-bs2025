"""
@file discovery.py
@brief Discovery-Modul für Peer-Erkennung im lokalen Netzwerk.

@details
Dieses Modul ermöglicht die automatische Erkennung von anderen Clients (Peers),
die ebenfalls den SLCP (Simple Local Chat Protocol) verwenden. Es unterstützt:

- Das Senden und Empfangen von WHOIS/IAM-Nachrichten über UDP.
- Zwei parallele Threads:
    1. Empfang von WHOIS/IAM
    2. Senden von WHOIS-Anfragen (z. B. ausgelöst durch die UI)
"""

import socket, threading, time
from utils.slcp import parse_message, build_message

def run_discovery(queue_from_ui, queue_to_ui, config):
    """
    @brief Startet den Discovery-Prozess in zwei Threads (Empfang/Senden).

    @param queue_from_ui: Queue für WHOIS-Anfragen aus der UI
    @param queue_to_ui: Queue für IAM-Antworten zurück an die UI
    @param config: Dict mit folgenden Einträgen:
        - 'whoisport': UDP-Port, auf dem WHOIS/IAM läuft
        - 'handle': lokaler Benutzername (wird in IAM verwendet)
        - 'port': TCP-Port für spätere Verbindungen
    """

    whois_port = config["whoisport"]
    local_handle = config["handle"]
    local_port = config["port"]

    # UDP-Socket für WHOIS/IAM initialisieren
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(("", whois_port))
    print(f"[Discovery] Listening on UDP {whois_port}")

    def receive():
        """
        @brief Hört auf eingehende WHOIS/IAM-Meldungen (SLCP) im Netzwerk.

        WHOIS: Wenn das Ziel-Handle dem eigenen entspricht, wird ein IAM zurückgesendet.
        IAM: Wird empfangen und an die UI gemeldet, damit Peers gespeichert werden können.
        """
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                msg = data.decode().strip()
                parsed = parse_message(msg)

                if parsed["command"] == "WHOIS" and parsed["params"][0] == local_handle:
                    try:
                        target_port = int(parsed["params"][1])
                        iam_msg = build_message("IAM", local_handle, get_own_ip(), local_port)
                        sock.sendto(iam_msg.encode(), (addr[0], target_port))
                        print(f"[Discovery] WHOIS von {addr}, IAM gesendet an {(addr[0], target_port)}")
                    except: continue

                elif parsed["command"] == "IAM":
                    handle, ip, port = parsed["params"]
                    queue_to_ui.put({
                        "type": "iam",
                        "handle": handle,
                        "ip": ip,
                        "port": int(port)
                    })

            except Exception as e:
                print(f"[Recv-Fehler] {e}")
            time.sleep(0.1)

    def send():
        """
        @brief Verarbeitet WHOIS-Anfragen, die von der UI eingehen.

        Wenn z. B. die UI einen Befehl wie 'whois b' ausführt, wird ein WHOIS
        an alle (Broadcast) geschickt. Die Empfänger antworten mit IAM.
        """
        while True:
            try:
                if not queue_from_ui.empty():
                    raw = queue_from_ui.get_nowait()["data"].strip()
                    handle = raw[6:].strip() if raw.upper().startswith("WHOIS ") else raw
                    msg = build_message("WHOIS", handle, str(local_port))
                    sock.sendto(msg.encode(), ('255.255.255.255', whois_port))
                    print(f"[Discovery] WHOIS gesendet: {msg}")
            except Exception as e:
                print(f"[Send-Fehler] {e}")
            time.sleep(0.1)

    # Starte parallele Threads
    threading.Thread(target=receive, daemon=True).start()
    threading.Thread(target=send, daemon=True).start()

    # Hauptthread bleibt aktiv, blockiert aber nicht
    while True: time.sleep(1)

def get_own_ip():
    """
    @brief Ermittelt die lokale IP-Adresse des Rechners.

    Nutzt eine Dummy-Verbindung zu 8.8.8.8 (Google DNS), um das genutzte Interface zu bestimmen.
    @return IP-Adresse als String, z. B. "192.168.178.42"
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"  # Fallback

