# local_messenger.py

import socket
import threading
import json
import time
import os

# --- Configuration ---
# The port for discovering other users on the network.
DISCOVERY_PORT = 50000
# The port for TCP communication (chat and file transfer).
TCP_PORT = 50001
# A buffer size for receiving data.
BUFFER_SIZE = 4096 
# The username for this instance of the application. Will be set by user input.
MY_USERNAME = ""

# --- Shared Data Structures ---
# A dictionary to store information about other online users.
# Format: { 'username': {'ip': '192.168.1.10', 'last_seen': 1662560000.0} }
online_users = {}
# A lock to prevent race conditions when multiple threads access online_users.
lock = threading.Lock()

# --- Peer Discovery (UDP) ---

def send_broadcast():
    """
    This function runs in a separate thread and periodically sends a broadcast message
    to the local network to announce our presence.
    """
    # Create a UDP socket.
    broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Enable the broadcast option on the socket.
    broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # Prepare the message we want to send.
    message = json.dumps({
        "username": MY_USERNAME,
        "status": "online"
    })

    while True:
        # Send the message to the broadcast address on the discovery port.
        # '<broadcast>' is a special address that sends to 255.255.255.255.
        broadcast_socket.sendto(message.encode('utf-8'), ('<broadcast>', DISCOVERY_PORT))
        time.sleep(5) # Announce our presence every 5 seconds.

def listen_for_peers():
    """
    This function runs in a separate thread and listens for broadcast messages
    from other peers to update our list of online users.
    """
    # Create a UDP socket to listen for messages.
    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Bind the socket to all available network interfaces on the discovery port.
    listen_socket.bind(('', DISCOVERY_PORT))

    while True:
        # Wait to receive data.
        data, addr = listen_socket.recvfrom(1024)
        message = json.loads(data.decode('utf-8'))
        
        # We don't want to add ourselves to the list.
        if message["username"] == MY_USERNAME:
            continue

        ip_address = addr[0]
        
        # Use the lock to safely update the shared user list.
        with lock:
            online_users[message["username"]] = {
                "ip": ip_address,
                "last_seen": time.time()
            }

# --- Reliable Communication (TCP) ---

def handle_client(conn, addr):
    """
    This function is spawned in a new thread for each incoming TCP connection.
    It handles receiving messages or files from a single client.
    """
    print(f"\n[+] Accepted connection from {addr[0]}:{addr[1]}")
    try:
        # Receive the initial message header.
        header_data = conn.recv(BUFFER_SIZE)
        if not header_data:
            return
        
        header = json.loads(header_data.decode('utf-8'))
        msg_type = header.get("type")

        if msg_type == "message":
            print(f"\n[Message from {header['username']}]: {header['payload']}")
            print("> ", end="") # Prompt user for next command

        elif msg_type == "file_offer":
            filename = header['filename']
            filesize = header['filesize']
            
            # Ask the user for confirmation.
            print(f"\n[File offer from {header['username']}]: {filename} ({filesize} bytes).")
            user_input = input("Do you want to accept? (y/n): ").lower()
            
            if user_input == 'y':
                # Send acceptance response.
                conn.send(json.dumps({"response": "accept"}).encode('utf-8'))
                
                # Receive the file.
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
                # Send rejection response.
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
        # Wait for a client to connect.
        conn, addr = server_socket.accept()
        # Once a client connects, create a new thread to handle them.
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

            # 1. Send file offer header.
            header = json.dumps({
                "type": "file_offer",
                "username": MY_USERNAME,
                "filename": filename,
                "filesize": filesize
            })
            client_socket.send(header.encode('utf-8'))

            # 2. Wait for acceptance.
            response_data = client_socket.recv(1024)
            response = json.loads(response_data.decode('utf-8'))

            if response.get("response") == "accept":
                print(f"[*] {username} accepted the file. Sending...")
                # 3. Send the actual file.
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
            message_text = " ".join(parts[2:])
            send_tcp_message(username, message_text)

        elif command == "send" and len(parts) == 3:
            username = parts[1]
            filepath = parts[2]
            send_file(username, filepath)

        elif command == "exit":
            # A more graceful exit would send a "goodbye" broadcast.
            print("Exiting...")
            os._exit(0)
        else:
            print("Unknown command. Try: list, msg <user> <message>, send <user> <filepath>, exit")

if __name__ == "__main__":
    MY_USERNAME = input("Enter your username: ")

    # Set all background threads as "daemon" threads.
    # This means they will exit automatically when the main program exits.
    
    broadcaster_thread = threading.Thread(target=send_broadcast, daemon=True)
    listener_thread = threading.Thread(target=listen_for_peers, daemon=True)
    tcp_server_thread = threading.Thread(target=run_tcp_server, daemon=True)

    broadcaster_thread.start()
    listener_thread.start()
    tcp_server_thread.start()
    
    print(f"\nWelcome, {MY_USERNAME}! Your local messenger is running.")
    print("Type 'list' to see other users.")
    print("Type 'msg <user> <message>' to chat.")
    print("Type 'send <user> <filepath>' to send a file.")
    print("Type 'exit' to close.\n")

    cli_input_loop() 