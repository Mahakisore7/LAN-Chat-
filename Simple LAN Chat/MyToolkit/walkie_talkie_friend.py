# walkie_talkie.py

import socket
import threading

# We need to know the other person's IP address.
# For now, since we're running both on the same computer, we'll use localhost.
# We'll also use different ports for each person to avoid conflicts.
MY_PORT = 50002
FRIEND_IP = '127.0.0.1'
FRIEND_PORT = 50001

# ---- Worker 1: The Listener ----
def listen_for_messages(sock):
    """This function runs in its own thread, continuously listening for messages."""
    print("Listener thread started. Waiting for messages...")
    while True:
        try:
            # Wait to receive data (this line will block)
            data, addr = sock.recvfrom(1024)
            
            # Decode and print the message
            print(f"\nFriend says: {data.decode()}\nYou: ", end="")
        except Exception as e:
            print(f"Listener error: {e}")
            break

# ---- Worker 2: The Sender ----
def send_messages(sock):
    """This function runs in its own thread, waiting for user input to send."""
    print("Sender thread started. You can now type messages.")
    while True:
        try:
            # Wait for the user to type a message (this line will block)
            message = input("You: ")
            
            # Send the message to the friend's address
            sock.sendto(message.encode(), (FRIEND_IP, FRIEND_PORT))
        except Exception as e:
            print(f"Sender error: {e}")
            break

# --- Main Program Setup ---
if __name__ == "__main__":
    # Create the single UDP socket for our application
    my_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Bind the socket to our designated port so we can receive messages
    my_socket.bind(('', MY_PORT))
    
    # Create the two "worker" threads
    listener = threading.Thread(target=listen_for_messages, args=(my_socket,), daemon=True)
    sender = threading.Thread(target=send_messages, args=(my_socket,), daemon=True)
    
    # Start the threads
    listener.start()
    sender.start()
    
    # The main thread needs to stay alive for the other threads to run.
    # We can use the sender's .join() method to make the main thread wait until the sender thread is done.
    # Since the sender is in an infinite loop, it will wait forever.
    sender.join()

    # Close the socket when the program is finally exited
    my_socket.close()
    print("Socket closed. Goodbye.")