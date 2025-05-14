import socket

whois_port = 4000
Buffer_size = 1023
HANDLE = "Meriem"
local_port = 5000

def start_discovery_service():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Socket wird hier erstellt
    sock.bind(('', whois_port))  # Server bindet den Socket an Port 4000
    print("Discovery-Service whois...")

    while True:
        data, addr = sock.recvfrom(Buffer_size)  # Warten auf eingehende Nachricht
        message = data.decode('utf-8').strip()  # Nachricht decodieren
        print(f"Nachricht von {addr}: {message}")

        if message.startswith("Whois"):  # Wenn die Nachricht "Whois" enthält
            parts = message.split()
            if len(parts) == 2 and parts[1] == HANDLE:  # Wenn das Handle übereinstimmt
                ip = socket.gethostbyname(socket.gethostname())  # Lokale IP-Adresse ermitteln
                response = f"IAM {HANDLE} {ip} {local_port}"  # Antwort nach dem Muster: IAM <HANDLE> <IP> <PORT>
                sock.sendto(response.encode('utf-8'), addr)  # Antwort senden
                print(f"Antwort an {addr}: {response}")

if __name__ == "__main__":
    start_discovery_service()
