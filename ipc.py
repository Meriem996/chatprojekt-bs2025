"""
ipc.py – Interprozesskommunikation für das Chatprogramm
Beschreibung: Modul zur Kommunikation zwischen Prozessen über multiprocessing.Queue
"""

from multiprocessing import Process, Queue
import time

def sender(queue: Queue):
    """
    Sendet Nachrichten in die Queue.
    """
    for i in range(5):
        msg = f"Nachricht {i}"
        print(f"[Sender] Sende: {msg}")
        queue.put(msg)
        time.sleep(1)
    queue.put(None)  # Signal zum Beenden

def receiver(queue: Queue):
    """
    Empfängt Nachrichten aus der Queue.
    """
    while True:
        msg = queue.get()
        if msg is None:
            print("[Empfänger] Beende...")
            break
        print(f"[Empfänger] Empfange: {msg}")

if __name__ == "__main__":
    q = Queue()
    p1 = Process(target=sender, args=(q,))
    p2 = Process(target=receiver, args=(q,))

    p1.start()
    p2.start()
    p1.join()
    p2.join()
