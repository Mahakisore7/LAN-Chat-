# network_core.py

import socket
import threading
import time
import os
import base64
import crypto_utils

TCP_PORT = 50001

class NetworkCore:
    def __init__(self, username, discovery_service, private_key, message_received_callback):
        self.username = username
        self.discovery_service = discovery_service
        self.private_key = private_key
        self.message_received_callback = message_received_callback
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)

    def start(self):
        self.server_thread.start()

    def stop(self):
        self.running = False
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
                    handler = threading.Thread(target=self._handle_client, args=(client_socket,), daemon=True)
                    handler.start()
                except Exception:
                    break

    def _handle_client(self, client_socket):
        with client_socket:
            try:
                header_data = client_socket.recv(4096)
                if not header_data: return
                
                header = header_data.decode()
                parts = header.split("::")
                data_type, encoded_message, sender_username = parts[0], parts[1], parts[2]

                if data_type == "MSG":
                    encrypted_message = base64.b64decode(encoded_message)
                    decrypted_message = crypto_utils.decrypt_message(self.private_key, encrypted_message)
                    self.message_received_callback(sender_username, decrypted_message)
            except Exception as e:
                print(f"[Handler] Error: {e}")

    def send_message(self, target_username, message):
        users = self.discovery_service.get_online_users()
        if target_username in users:
            target_ip, target_public_key, _ = users[target_username]
            encrypted_message = crypto_utils.encrypt_message(target_public_key, message)
            encoded_message = base64.b64encode(encrypted_message).decode('utf-8')
            header = f"MSG::{encoded_message}::{self.username}".encode()
            threading.Thread(target=self._send_tcp_data, args=(target_ip, header), daemon=True).start()
        else:
            print(f"User '{target_username}' not found.")
            
    def _send_tcp_data(self, target_ip, data):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((target_ip, TCP_PORT))
                s.sendall(data)
        except Exception as e:
            print(f"[TCP Send] Error: {e}")