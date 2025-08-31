# receiver.py

import socket

# 1. Create a socket object.
#    AF_INET means we are using the standard IPv4 address family.
#    SOCK_DGRAM means we are creating a UDP socket (a "datagram" socket).
receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# 2. Bind the socket to an address and port.
#    '0.0.0.0' is a special address that means "listen on all available network interfaces."
#    50000 is the port number we've chosen. It's like a door number.
receiver_socket.bind(('0.0.0.0', 50000))

print("Listening for a message on port 50000...")

# 3. Wait to receive data.
#    This line will "block" – the program will pause here and wait until it receives a packet.
#    1024 is the buffer size – the maximum amount of data to receive at once.
data, sender_address = receiver_socket.recvfrom(1024)

# 4. Decode and print the message.
#    The data arrives as raw bytes, so we must .decode() it into a string.
print(f"Received message: '{data.decode()}' from {sender_address}")

# 5. Close the socket.
receiver_socket.close()