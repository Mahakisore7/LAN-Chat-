# discovery.py

import socket
import threading
import time
import crypto_utils 

# --- CONFIGURATION ---
DISCOVERY_PORT = 50000                          # UDP port for discovery broadcasts
DISCOVERY_MESSAGE = "LOCAL_CHAT_DISCOVER_V2_SECURE"  # Unique message to identify LAN chat broadcasts
BROADCAST_INTERVAL = 5                          # Seconds between broadcast messages

def get_lan_ip():
    """
    Finds the local IP address of the machine.
    Attempts to connect to a non-routable address to determine the local IP.
    Returns:
        str: Local IP address.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't have to be reachable; just used to get local IP
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class Discovery:
    """
    Handles LAN peer discovery for the chat application.
    Broadcasts presence and listens for other users on the LAN.
    Maintains a list of online users with their IP and public key.
    """

    def __init__(self, username, public_key):
        """
        Initializes the Discovery service.

        Args:
            username (str): Local user's username.
            public_key: Local user's RSA public key.
        """
        self.username = username
        self.public_key_str = crypto_utils.public_key_to_string(public_key)  # Serialize public key for broadcast
        self.lan_ip = get_lan_ip()                                           # Get local IP address
        self.online_users = {}                                               # Dictionary of discovered users
        self.running = True                                                  # Service running flag
        self.lock = threading.Lock()                                         # Thread lock for shared data
        self.listener_thread = threading.Thread(target=self._listen_for_peers, daemon=True)   # Thread for listening
        self.broadcaster_thread = threading.Thread(target=self._broadcast_presence, daemon=True) # Thread for broadcasting

    def start(self):
        """
        Starts the discovery service.
        Launches listener and broadcaster threads.
        """
        print(f"[Discovery] Starting service for user '{self.username}' on IP {self.lan_ip}...")
        self.listener_thread.start()
        self.broadcaster_thread.start()
        print("[Discovery] Service running in the background.")

    def stop(self):
        """
        Stops the discovery service.
        """
        self.running = False

    def get_online_users(self):
        """
        Returns a dictionary of currently online users.
        Filters out users who haven't been seen recently.

        Returns:
            dict: {username: (ip, public_key, last_seen)}
        """
        with self.lock:
            current_time = time.time()
            # Filter out users who haven't been heard from in a while
            active_users = {}
            for user, (ip, pub_key, last_seen) in self.online_users.items():
                if current_time - last_seen < (BROADCAST_INTERVAL * 3):
                    active_users[user] = (ip, pub_key, last_seen)
            self.online_users = active_users
            return self.online_users

    def _listen_for_peers(self):
        """
        Listens for UDP broadcast messages from other LAN chat users.
        Updates the online_users dictionary when new users are discovered.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('', DISCOVERY_PORT))
            s.settimeout(1.0)  # Timeout to allow periodic check of self.running
            while self.running:
                try:
                    data, addr = s.recvfrom(4096)
                    message = data.decode()
                    if message.startswith(DISCOVERY_MESSAGE):
                        # Message format: DISCOVERY_MESSAGE::username::ip::public_key
                        parts = message.split("::", 3)
                        peer_username, peer_ip, peer_public_key_str = parts[1], parts[2], parts[3]
                        
                        # Ignore messages from self
                        if peer_username != self.username:
                            with self.lock:
                                peer_public_key = crypto_utils.string_to_public_key(peer_public_key_str)
                                if peer_username not in self.online_users:
                                    print(f"[Discovery] Discovered new user: {peer_username} at {peer_ip}")
                                # Update or add user info
                                self.online_users[peer_username] = (peer_ip, peer_public_key, time.time())
                except socket.timeout:
                    continue
                except Exception:
                    pass # Ignore parsing errors from malformed packets

    def _broadcast_presence(self):
        """
        Periodically broadcasts the user's presence on the LAN using UDP.
        Includes username, IP, and public key in the broadcast message.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            message = f"{DISCOVERY_MESSAGE}::{self.username}::{self.lan_ip}::{self.public_key_str}".encode()
            while self.running:
                try:
                    s.sendto(message, ('<broadcast>', DISCOVERY_PORT))
                    time.sleep(BROADCAST_INTERVAL)
                except Exception:
                    break