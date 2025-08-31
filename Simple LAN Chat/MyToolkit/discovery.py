import socket
import threading
import time

# --- CONFIGURATION ---
DISCOVERY_PORT = 50000
DISCOVERY_MESSAGE = "LOCAL_CHAT_DISCOVER_V1"
BROADCAST_INTERVAL = 5

class Discovery:
    def __init__(self, username):
        self.username = username
        self.online_users = {}
        self.running = True
        self.lock = threading.Lock()
        self.listener_thread = threading.Thread(target=self._listen_for_peers, daemon=True)
        self.broadcaster_thread = threading.Thread(target=self._broadcast_presence, daemon=True)

    def start(self):
        print(f"[Discovery] Starting service for user '{self.username}'...")
        self.listener_thread.start()
        self.broadcaster_thread.start()
        print("[Discovery] Service running in the background.")

    def stop(self):
        print("[Discovery] Stopping service...")
        self.running = False

    def get_online_users(self):
        with self.lock:
            current_time = time.time()
            active_users = {}
            for user, (ip, last_seen) in self.online_users.items():
                if current_time - last_seen < (BROADCAST_INTERVAL * 3):
                    active_users[user] = (ip, last_seen)
                else:
                    print(f"[Discovery] User '{user}' timed out.")
            self.online_users = active_users
            return self.online_users

    def _listen_for_peers(self):
        # Create a UDP socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            # --- THIS IS THE FIX ---
            # Set a special socket option to allow the address to be reused.
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # ---------------------

            # Bind the socket to listen on the discovery port from any IP address
            s.bind(('', DISCOVERY_PORT))
            s.settimeout(1.0)

            print(f"[Listener] Listening for peers on UDP port {DISCOVERY_PORT}...")
            while self.running:
                try:
                    data, addr = s.recvfrom(1024)
                    message = data.decode()
                    if message.startswith(DISCOVERY_MESSAGE):
                        parts = message.split("::")
                        peer_username = parts[1]
                        if peer_username != self.username:
                            with self.lock:
                                if peer_username not in self.online_users:
                                    print(f"[Discovery] Discovered new user: {peer_username} at {addr[0]}")
                                self.online_users[peer_username] = (addr[0], time.time())
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"[Listener] An error occurred: {e}")

    def _broadcast_presence(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            # Set a special socket option to allow broadcasting
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            message = f"{DISCOVERY_MESSAGE}::{self.username}".encode()
            print("[Broadcaster] Starting to broadcast presence...")
            while self.running:
                try:
                    s.sendto(message, ('<broadcast>', DISCOVERY_PORT))
                    time.sleep(BROADCAST_INTERVAL)
                except Exception as e:
                    print(f"[Broadcaster] An error occurred: {e}")
                    break

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    my_username = input("Enter your username: ") or "DefaultUser"
    discovery_service = Discovery(my_username)
    discovery_service.start()
    
    try:
        while True:
            print("\n--- Online Users ---")
            users = discovery_service.get_online_users()
            if users:
                for user, (ip, last_seen) in users.items():
                    print(f"- {user} ({ip})")
            else:
                print("Scanning for other users...")
            print("--------------------")
            time.sleep(10)
    except KeyboardInterrupt:
        print("\nShutting down...")
        discovery_service.stop()