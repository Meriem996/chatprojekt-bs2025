"""
@file cli_local_runner_udp.py
@brief Lokale CLI-Instanz für den BSRN-Chat im reinen UDP-Modus (CLI <-> GUI oder CLI <-> CLI auf demselben Rechner).

@details
Diese Datei wird von main.py über subprocess gestartet und ermöglicht
einen einfachen CLI-Chat zwischen zwei lokalen Benutzern per UDP.
"""

import socket
import threading
import sys


def receive_loop(sock):
    """
    @brief Empfängt eingehende UDP-Nachrichten und zeigt sie im Terminal an.
    @details Läuft in einem eigenen Thread, erkennt SLCP MSG-Kommandos und
             zeigt sie formatiert an. Verwendet |||-Trennzeichen zur Absendererkennung.
    @param sock UDP-Socket für den Empfang (bereits gebunden)
    """

    while True:
        try:
            # Empfange UDP-Nachricht (max. 1024 Byte)
            data, addr = sock.recvfrom(1024)
            msg = data.decode("utf-8")

            # Nachrichten enthalten Absendername getrennt mit "|||"
            if "|||" in msg:
                sender, content = msg.split("|||", 1)

                # Prüfe, ob SLCP-kompatible MSG-Nachricht
                if content.startswith("MSG "):
                    parts = content.split(" ", 2)
                    if len(parts) == 3:
                        target, text = parts[1], parts[2]
                        print(f"\n[{sender}]: {text}")
                    else:
                        # Fallback: ungültig formatiert → zeige direkt
                        print(f"\n[{sender}]: {content}")
                else:
                    # Nicht-MSG-Nachrichten → zeige unformatiert
                    print(f"\n[{sender}]: {content}")

            else:
                # Falls kein Sender übertragen wurde → nimm Portnummer als Kennung
                print(f"\n[CLI-{addr[1]}]: {msg}")

            # Eingabeprompt wieder anzeigen
            print(">> ", end="", flush=True)

        except:
            # Fehler ignorieren (Verbindungsfehler, ungültige Daten etc.)
            continue


def main():
    """
    @brief Hauptfunktion zum Starten einer lokalen CLI-Instanz mit UDP-Kommunikation.
    @details Diese Funktion ermöglicht bidirektionale Kommunikation per UDP mit einer
             weiteren Instanz (CLI oder GUI) auf demselben Gerät. Nachrichten werden
             über localhost:UDP gesendet, optional im SLCP-kompatiblen Format.
    """

    # Prüfe Kommandozeilenargumente (eigener Port, Ziel-Port)
    if len(sys.argv) != 3:
        print("Nutzung: python cli_local_runner_udp.py <eigener_port> <ziel_port>")
        sys.exit(1)

    # Portkonfiguration aus Argumenten einlesen
    my_port = int(sys.argv[1])
    target_port = int(sys.argv[2])

    # Benutzername abfragen (für Anzeige und Versand)
    my_name = input("Wie heißt du? ").strip()
    if not my_name:
        my_name = f"User-{my_port}"  # Fallback: Portnummer als Name

    # Erzeuge neuen UDP-Socket und binde ihn an den lokalen Port
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", my_port))

    print(f"[Lokaler UDP-Chat gestartet auf Port {my_port}]")
    print(f"[Nachrichten werden gesendet an Port {target_port}]")
    print(">> Zum Beenden 'exit' eingeben")

    # Starte Empfangsthread für eingehende Nachrichten
    threading.Thread(target=receive_loop, args=(sock,), daemon=True).start()

    # Hauptschleife für Nutzereingaben
    while True:
        # Eingabe vom Nutzer lesen
        msg = input(">> ").strip()

        # Beenden, wenn „exit“ eingegeben wurde
        if msg.lower() == "exit":
            print("Beende Chat.")
            break

        # Nachrichten im SLCP-Format (msg <Empfänger> <Text>)
        if msg.startswith("msg "):
            parts = msg.split(" ", 2)
            if len(parts) == 3:
                target, text = parts[1], parts[2]
                full_msg = f"{my_name}|||MSG {target} {text}"  # SLCP-Nachricht mit Absender
            else:
                full_msg = f"{my_name}|||{msg}"  # Fallback
        else:
            # Sonstige Nachrichten (z. B. reine Texteingabe)
            full_msg = f"{my_name}|||{msg}"

        # Nachricht an den Zielport senden
        sock.sendto(full_msg.encode("utf-8"), ("127.0.0.1", target_port))

# Einstiegspunkt bei Direktaufruf der Datei
if __name__ == "__main__":
    main()