import socket
import threading
import time
import os

# --- CONFIGURATION ---
TCP_PORT = 50001 # A separate port for reliable TCP communication

class NetworkCore:
    """
    Manages all direct, reliable (TCP) communication for chat and file transfers.
    This is the "backend brain" for the GUI.
    """
    def __init__(self, username, discovery_service, message_received_callback, file_received_callback):
        self.username = username
        self.discovery_service = discovery_service
        self.message_received_callback = message_received_callback
        self.file_received_callback = file_received_callback
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)

    def start(self):
        """Starts the main TCP server thread."""
        self.server_thread.start()

    def stop(self):
        """Stops the communication service."""
        self.running = False
        # A trick to unblock the server socket accept() call
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', TCP_PORT))
        except:
            pass # Expected if the server is already shutting down

    def _run_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('', TCP_PORT))
            server_socket.listen(5)
            print(f"[NetworkCore] TCP Server listening on port {TCP_PORT}...")

            while self.running:
                try:
                    client_socket, addr = server_socket.accept()
                    handler = threading.Thread(target=self._handle_client, args=(client_socket, addr), daemon=True)
                    handler.start()
                except Exception as e:
                    if self.running:
                        print(f"[Server] An error occurred: {e}")
                    break

    def _handle_client(self, client_socket, addr):
        with client_socket:
            try:
                header_data = client_socket.recv(1024)
                if not header_data:
                    return
                
                header = header_data.decode()
                parts = header.split("::")
                data_type = parts[0]

                if data_type == "MSG":
                    message = parts[1]
                    sender_username = parts[2]
                    # Use the callback to safely update the GUI
                    self.message_received_callback(sender_username, message)
                
                elif data_type == "FILE":
                    # --- THIS IS THE IMPROVED LOGIC ---
                    filename = os.path.basename(parts[1]) # Sanitize filename for security
                    filesize = int(parts[2])
                    sender_username = parts[3]
                    
                    # 1. Define the directory structure
                    download_dir = os.path.join("received_files", sender_username)
                    
                    # 2. Create the directories if they don't exist
                    os.makedirs(download_dir, exist_ok=True)
                    
                    # 3. Construct the full, clean path to save the file
                    save_path = os.path.join(download_dir, filename)
                    # ------------------------------------

                    # Notify the GUI that a file is incoming
                    self.file_received_callback(sender_username, filename, filesize, "start")

                    # Use the new save_path to open and write the file
                    with open(save_path, 'wb') as f:
                        bytes_received = 0
                        while bytes_received < filesize:
                            chunk = client_socket.recv(4096)
                            if not chunk:
                                break
                            f.write(chunk)
                            bytes_received += len(chunk)
                    
                    # Notify the GUI that the file is finished
                    self.file_received_callback(sender_username, filename, filesize, "end")

            except Exception as e:
                print(f"[Handler] Error with client {addr}: {e}")

    def send_message(self, target_username, message):
        users = self.discovery_service.get_online_users()
        if target_username in users:
            target_ip = users[target_username][0]
            header = f"MSG::{message}::{self.username}".encode()
            threading.Thread(target=self._send_tcp_data, args=(target_ip, header), daemon=True).start()
        else:
            print(f"User '{target_username}' not found.")

    def send_file(self, target_username, filepath):
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return

        users = self.discovery_service.get_online_users()
        if target_username in users:
            target_ip = users[target_username][0]
            # Start the file transfer in a new thread to avoid freezing the GUI
            threading.Thread(target=self._send_file_thread, args=(target_ip, filepath), daemon=True).start()
        else:
            print(f"User '{target_username}' not found.")
            
    def _send_tcp_data(self, target_ip, data):
        """Helper function to establish a TCP connection and send data."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((target_ip, TCP_PORT))
                s.sendall(data)
        except Exception as e:
            print(f"[TCP Send] Error sending data to {target_ip}: {e}")

    def _send_file_thread(self, target_ip, filepath):
        """Worker function to handle sending a file in the background."""
        try:
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            header = f"FILE::{filename}::{filesize}::{self.username}".encode()

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                print(f"Connecting to {target_ip} to send file...")
                s.connect((target_ip, TCP_PORT))
                s.sendall(header)
                time.sleep(0.1) 
                
                print(f"Sending file '{filename}'...")
                with open(filepath, 'rb') as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        s.sendall(chunk)
                print(f"File '{filename}' sent successfully.")
        except Exception as e:
            print(f"[File Send] Error: {e}")

