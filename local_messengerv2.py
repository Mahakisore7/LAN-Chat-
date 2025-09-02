# local_messenger.py (Version 2)

import socket
import threading

import json
import time
import os

# --- Configuration ---
DISCOVERY_PORT = 50000
TCP_PORT = 50001
BUFFER_SIZE = 4096
MY_USERNAME = ""
# --- NEW --- Time in seconds before a user is considered offline.
USER_TIMEOUT_SECONDS = 15 

# --- Shared Data Structures ---
online_users = {}
lock = threading.Lock()

# --- Peer Discovery (UDP) ---

def send_broadcast(status="online"):
    """
    This function now accepts a status to indicate online or offline presence.
    """
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    message = json.dumps({
        "username": MY_USERNAME,
        "status": status  # --- NEW --- Status can be 'online' or 'offline'
    })
    
    # Send the message once.
    broadcast_socket.sendto(message.encode('utf-8'), ('<broadcast>', DISCOVERY_PORT))
    broadcast_socket.close()

def broadcast_online_presence():
    """
    This function runs in a separate thread and periodically sends an 'online'
    broadcast message to the local network to announce our presence.
    """
    while True:
        send_broadcast(status="online")
        time.sleep(5)

def listen_for_peers():
    """
    Listens for broadcast messages and updates the user list.
    --- NEW --- Now handles 'offline' messages to remove users instantly.
    """
    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    listen_socket.bind(('', DISCOVERY_PORT))

    while True:
        data, addr = listen_socket.recvfrom(1024)
        message = json.loads(data.decode('utf-8'))
        
        username = message.get("username")
        status = message.get("status")

        if not username or username == MY_USERNAME:
            continue

        ip_address = addr[0]
        
        with lock:
            if status == "online":
                online_users[username] = {
                    "ip": ip_address,
                    "last_seen": time.time()
                }
            elif status == "offline":
                if username in online_users:
                    del online_users[username]
                    print(f"\n[*] {username} has gone offline.")
                    print("> ", end="")

def cleanup_inactive_users():
    """
    --- NEW ---
    This function runs in a separate thread to periodically remove users
    who haven't sent a broadcast recently (i.e., they timed out).
    """
    while True:
        time.sleep(10) # Check every 10 seconds
        with lock:
            current_time = time.time()
            # Create a list of users to remove to avoid modifying the dict while iterating
            users_to_remove = []
            for user, info in online_users.items():
                if current_time - info['last_seen'] > USER_TIMEOUT_SECONDS:
                    users_to_remove.append(user)
            
            for user in users_to_remove:
                del online_users[user]
                print(f"\n[*] {user} timed out and was removed from the list.")
                print("> ", end="")

# --- Reliable Communication (TCP) ---

def handle_client(conn, addr):
    """
    This function is spawned in a new thread for each incoming TCP connection.
    It handles receiving messages or files from a single client.
    """
    print(f"\n[+] Accepted connection from {addr[0]}:{addr[1]}")
    try:
        header_data = conn.recv(BUFFER_SIZE)
        if not header_data:
            return
        
        header = json.loads(header_data.decode('utf-8'))
        msg_type = header.get("type")

        if msg_type == "message":
            print(f"\n[Message from {header['username']}]: {header['payload']}")
            print("> ", end="")

        elif msg_type == "file_offer":
            filename = header['filename']
            filesize = header['filesize']
            
            print(f"\n[File offer from {header['username']}]: {filename} ({filesize} bytes).")
            user_input = input("Do you want to accept? (y/n): ").lower()
            
            if user_input == 'y':
                conn.send(json.dumps({"response": "accept"}).encode('utf-8'))
                
                with open(filename, 'wb') as f:
                    bytes_received = 0
                    while bytes_received < filesize:
                        data = conn.recv(BUFFER_SIZE)
                        if not data:
                            break
                        f.write(data)
                        bytes_received += len(data)
                print(f"\n[+] File '{filename}' received successfully.")
                print("> ", end="")
            else:
                conn.send(json.dumps({"response": "reject"}).encode('utf-8'))
                print("\n[-] File transfer rejected.")
                print("> ", end="")

    except (json.JSONDecodeError, ConnectionResetError) as e:
        print(f"\n[!] Error handling client {addr}: {e}")
    finally:
        conn.close()

def run_tcp_server():
    """
    This function runs in a separate thread and listens for incoming TCP connections.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('', TCP_PORT))
    server_socket.listen(5)
    print(f"[*] TCP Server listening on port {TCP_PORT}")

    while True:
        conn, addr = server_socket.accept()
        client_handler = threading.Thread(target=handle_client, args=(conn, addr))
        client_handler.start()

# --- User Interface (CLI) & Main Execution ---

def send_tcp_message(username, text):
    """Sends a simple text message to a specified user."""
    target_ip = None
    with lock:
        if username in online_users:
            target_ip = online_users[username]['ip']
    
    if target_ip:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((target_ip, TCP_PORT))
            
            header = json.dumps({
                "type": "message",
                "username": MY_USERNAME,
                "payload": text
            })
            
            client_socket.send(header.encode('utf-8'))
            client_socket.close()
        except Exception as e:
            print(f"[!] Error sending message to {username}: {e}")
    else:
        print(f"[!] User '{username}' not found or offline.")

def send_file(username, filepath):
    """Sends a file to a specified user."""
    if not os.path.exists(filepath):
        print(f"[!] File not found: {filepath}")
        return

    target_ip = None
    with lock:
        if username in online_users:
            target_ip = online_users[username]['ip']

    if target_ip:
        try:
            filesize = os.path.getsize(filepath)
            filename = os.path.basename(filepath)

            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((target_ip, TCP_PORT))

            header = json.dumps({
                "type": "file_offer",
                "username": MY_USERNAME,
                "filename": filename,
                "filesize": filesize
            })
            client_socket.send(header.encode('utf-8'))

            response_data = client_socket.recv(1024)
            response = json.loads(response_data.decode('utf-8'))

            if response.get("response") == "accept":
                print(f"[*] {username} accepted the file. Sending...")
                with open(filepath, 'rb') as f:
                    while True:
                        bytes_read = f.read(BUFFER_SIZE)
                        if not bytes_read:
                            break
                        client_socket.sendall(bytes_read)
                print(f"[*] File '{filename}' sent successfully.")
            else:
                print(f"[-] {username} rejected the file.")

            client_socket.close()
        except Exception as e:
            print(f"[!] Error sending file to {username}: {e}")
    else:
        print(f"[!] User '{username}' not found or offline.")

def cli_input_loop():
    """The main loop to process user commands."""
    while True:
        cmd_input = input("> ")
        parts = cmd_input.split()
        if not parts:
            continue
        
        command = parts[0].lower()

        if command == "list":
            print("\n--- Online Users ---")
            with lock:
                if not online_users:
                    print("No other users found.")
                for user, info in online_users.items():
                    print(f"- {user} (at {info['ip']})")
            print("--------------------\n")

        elif command == "msg" and len(parts) >= 3:
            username = parts[1]
            # --- NEW --- Prevent self-messaging
            if username == MY_USERNAME:
                print("[!] You cannot send a message to yourself.")
                continue
            message_text = " ".join(parts[2:])
            send_tcp_message(username, message_text)
        
        # --- NEW --- Broadcast command
        elif command == "bcast" and len(parts) >= 2:
            message_text = " ".join(parts[1:])
            print("[*] Sending broadcast message...")
            with lock:
                for user in online_users:
                    send_tcp_message(user, f"(Broadcast) {message_text}")

        elif command == "send" and len(parts) == 3:
            username = parts[1]
            # --- NEW --- Prevent self-file-sending
            if username == MY_USERNAME:
                print("[!] You cannot send a file to yourself.")
                continue
            filepath = parts[2]
            send_file(username, filepath)

        elif command == "exit":
            # --- NEW --- Send a goodbye message before exiting
            print("Sending goodbye message...")
            send_broadcast(status="offline")
            time.sleep(0.5) # Give the packet a moment to send
            print("Exiting...")
            os._exit(0)
        else:
            print("Unknown command. Try: list, msg, bcast, send, exit")

if __name__ == "__main__":
    MY_USERNAME = input("Enter your username: ")

    # Start all background threads as "daemon" threads.
    broadcaster_thread = threading.Thread(target=broadcast_online_presence, daemon=True)
    listener_thread = threading.Thread(target=listen_for_peers, daemon=True)
    tcp_server_thread = threading.Thread(target=run_tcp_server, daemon=True)
    # --- NEW --- Start the cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_inactive_users, daemon=True)

    broadcaster_thread.start()
    listener_thread.start()
    tcp_server_thread.start()
    cleanup_thread.start()
    
    print(f"\nWelcome, {MY_USERNAME}! Your local messenger is running.")
    print("Type 'list' to see other users.")
    print("Type 'msg <user> <message>' to chat.")
    print("Type 'bcast <message>' to message everyone.")
    print("Type 'send <user> <filepath>' to send a file.")
    print("Type 'exit' to close.\n")

    cli_input_loop()
