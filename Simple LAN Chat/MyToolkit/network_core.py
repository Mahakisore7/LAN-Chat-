# network_core.py

import socket
import threading
import time
import os
import base64
import crypto_utils
import uuid

TCP_PORT = 50001
# NEW: Define a constant for buffer size
BUFFER_SIZE = 4096

class NetworkCore:
    def __init__(self, username, discovery_service, private_key, message_received_callback, ack_received_callback, file_received_callback):
        self.username = username
        self.discovery_service = discovery_service
        self.private_key = private_key
        # UPDATED: More specific callbacks
        self.message_received_callback = message_received_callback
        self.ack_received_callback = ack_received_callback
        self.file_received_callback = file_received_callback
        
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)

    def start(self):
        self.server_thread.start()

    def stop(self):
        self.running = False
        # Unblock the server accept call
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('127.0.0.1', TCP_PORT))
        except:
            pass

    def _run_server(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('', TCP_PORT))
            server_socket.listen(5)
            print(f"[NetworkCore] TCP Server listening on port {TCP_PORT}...")
            while self.running:
                try:
                    client_socket, addr = server_socket.accept()
                    if not self.running: break
                    handler = threading.Thread(target=self._handle_client, args=(client_socket,), daemon=True)
                    handler.start()
                except Exception as e:
                    if self.running: print(f"[NetworkCore] Server error: {e}")
                    break

    def _handle_client(self, client_socket):
        with client_socket:
            try:
                # UPDATED: Handle different message types based on headers
                header_data = client_socket.recv(BUFFER_SIZE)
                if not header_data: return
                
                header_str = header_data.decode()
                parts = header_str.split("::")
                data_type = parts[0]

                if data_type == "MSG":
                    msg_id, encoded_message, sender_username = parts[1], parts[2], parts[3]
                    encrypted_message = base64.b64decode(encoded_message)
                    decrypted_message = crypto_utils.decrypt_message(self.private_key, encrypted_message)
                    self.message_received_callback(sender_username, decrypted_message)
                    # NEW: Send acknowledgment back
                    self.send_ack(sender_username, msg_id)

                elif data_type == "ACK":
                    msg_id, sender_username = parts[1], parts[2]
                    self.ack_received_callback(msg_id)
                
                elif data_type == "FILE":
                    filename, filesize, encoded_encrypted_key, encoded_nonce, sender_username = parts[1], int(parts[2]), parts[3], parts[4], parts[5]
                    encrypted_aes_key = base64.b64decode(encoded_encrypted_key)
                    nonce = base64.b64decode(encoded_nonce)
                    
                    # Decrypt the AES key with our private RSA key
                    aes_key = crypto_utils.decrypt_message(self.private_key, encrypted_aes_key).encode() # Key is bytes
                    
                    # Prepare to receive file
                    os.makedirs(f"received_files/{sender_username}", exist_ok=True)
                    filepath = os.path.join(f"received_files/{sender_username}", filename)
                    
                    encrypted_file_data = b""
                    bytes_received = 0
                    while bytes_received < filesize:
                        chunk = client_socket.recv(BUFFER_SIZE)
                        if not chunk: break
                        encrypted_file_data += chunk
                        bytes_received += len(chunk)

                    # Decrypt file data and save
                    decrypted_data = crypto_utils.decrypt_file_data(aes_key, nonce, encrypted_file_data)
                    with open(filepath, "wb") as f:
                        f.write(decrypted_data)
                    
                    self.file_received_callback(sender_username, filename)

            except Exception as e:
                print(f"[Handler] Error: {e}")

    def send_message(self, target_username, message):
        users = self.discovery_service.get_online_users()
        if target_username in users:
            target_ip, target_public_key, _ = users[target_username]
            # UPDATED: Include a unique message ID
            msg_id = str(uuid.uuid4())
            encrypted_message = crypto_utils.encrypt_message(target_public_key, message)
            encoded_message = base64.b64encode(encrypted_message).decode('utf-8')
            header = f"MSG::{msg_id}::{encoded_message}::{self.username}".encode()
            
            threading.Thread(target=self._send_tcp_data, args=(target_ip, header), daemon=True).start()
            return msg_id # Return the ID to the GUI for tracking
        else:
            print(f"User '{target_username}' not found.")
            return None
    
    # NEW: Send acknowledgment
    def send_ack(self, target_username, msg_id):
        users = self.discovery_service.get_online_users()
        if target_username in users:
            target_ip, _, _ = users[target_username]
            header = f"ACK::{msg_id}::{self.username}".encode()
            threading.Thread(target=self._send_tcp_data, args=(target_ip, header), daemon=True).start()

    # NEW: Send an encrypted file
    def send_file(self, target_username, filepath):
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return
            
        users = self.discovery_service.get_online_users()
        if target_username in users:
            target_ip, target_public_key, _ = users[target_username]

            with open(filepath, 'rb') as f:
                file_data = f.read()

            # 1. Encrypt file data with a new AES key
            encrypted_data, aes_key, nonce = crypto_utils.encrypt_file_data(file_data)
            
            # 2. Encrypt the AES key with the recipient's public RSA key
            encrypted_aes_key = crypto_utils.encrypt_message(target_public_key, aes_key.decode('latin-1'))
            
            # 3. Prepare header
            filename = os.path.basename(filepath)
            filesize = len(encrypted_data)
            encoded_key = base64.b64encode(encrypted_aes_key).decode('utf-8')
            encoded_nonce = base64.b64encode(nonce).decode('utf-8')
            
            header = f"FILE::{filename}::{filesize}::{encoded_key}::{encoded_nonce}::{self.username}".encode()
            
            # 4. Send header then data
            threading.Thread(target=self._send_tcp_data, args=(target_ip, header + encrypted_data), daemon=True).start()
            print(f"Sent file '{filename}' to {target_username}")
        else:
            print(f"User '{target_username}' not found.")

    def _send_tcp_data(self, target_ip, data):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10) # 10-second timeout for connection
                s.connect((target_ip, TCP_PORT))
                s.sendall(data)
        except Exception as e:
            print(f"[TCP Send] Error connecting to {target_ip}: {e}")