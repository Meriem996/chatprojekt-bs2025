"""
@file ipc.py
@brief Einfache Queues zur Interprozesskommunikation (IPC)im chatprojekt

Dieses Modul erstellt Verbindungen, damit UI mit Netzwerk und Discovery reden kann.
"""
from multiprocessing import Queue

# UI → Netzwerk
queue_ui_to_net = Queue()

# Netzwerk → UI
queue_net_to_ui = Queue()

# UI → Discovery
queue_ui_to_discovery = Queue()

# Discovery → UI
queue_discovery_to_ui = Queue()
