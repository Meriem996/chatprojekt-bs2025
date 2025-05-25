import socket
import threading
Max_MSG_LEN = 512  #SLCP-Nachrichtengröße laut Aufgabe
ENCODING = "utf -8"
 ### Konfiguration  ### 
BROADCAST_IP = "255.255.255.255"
BROADCAST_PORT = 4000
# Starte UDP-Listener (für MSG, IAM, IMG, JOIN )
def start_message_listener(port):
  def listener():
    sock = socket.socket(socket.AF_INET,socket.SOCK_DDGRAM)
    sock.bind((",port))
    
