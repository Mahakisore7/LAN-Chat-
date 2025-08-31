# sender.py

import socket

# 1. Create a UDP socket.
sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# 2. Define the message and the receiver's address.
message = "Hello, World!"
# '127.0.0.1' is a special address called "localhost". It always means "this same computer."
# 50000 is the port number the receiver is listening on.
receiver_address = ('127.0.0.1', 50000)

# 3. Encode the message and send it.
#    We must .encode() our string into raw bytes before sending.
sender_socket.sendto(message.encode(), receiver_address)

print(f"Sent message: '{message}' to {receiver_address}")

# 4. Close the socket.
sender_socket.close()