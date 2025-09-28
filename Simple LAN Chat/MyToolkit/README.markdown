# Secure LAN Messenger

A decentralized, end-to-end encrypted chat and file-sharing application that works over a local network without requiring an internet connection. This project leverages fundamental networking concepts to create a private, serverless communication tool ideal for secure communication in environments where internet access is unavailable or undesirable.

## Overview

In a world where most communication apps rely on centralized internet servers, Secure LAN Messenger takes a different approach: true peer-to-peer communication. This application allows users on the same Wi-Fi or local network to automatically discover each other, exchange encrypted messages, and (in future updates) share files directly. It’s designed to be a private, resilient communication tool that functions seamlessly even when the internet is down.

## Key Features

- **Zero-Configuration Discovery**: Users are automatically discovered on the local network using UDP broadcasting, eliminating the need to manually enter IP addresses.
- **End-to-End Encryption**: All messages are secured using 2048-bit RSA public-key cryptography. A message encrypted with a recipient’s public key can only be decrypted with their private key, ensuring complete privacy.
- **Decentralized Identity**: Each user’s identity is based on a locally generated cryptographic key pair. No central authority or sign-up is required.
- **Direct, Reliable Communication**: Chat (and future file transfers) use direct TCP connections, ensuring data arrives in the correct order without errors.
- **Modern Graphical User Interface**: A clean, user-friendly interface built with CustomTkinter, featuring a dark mode and an intuitive layout.
- **Organized File Transfers** (planned): Received files will be automatically sorted into directories based on the sender’s username (e.g., `received_files/Alice/report.pdf`).

## How It Works: The Technical Architecture

The application is built on a clean, multi-threaded architecture that separates core responsibilities into distinct modules for modularity and maintainability.

### 1. The Cryptography Core (`crypto_utils.py`)
The security backbone of the application.

- **Identity**: On first launch, a 2048-bit RSA key pair (public and private) is generated and saved locally in the `keys/` directory. The private key never leaves the user’s machine.
- **Encryption**: Messages are encrypted using the recipient’s public key before being sent.
- **Decryption**: Incoming encrypted messages are decrypted using the user’s private key.

### 2. The Discovery Service (`discovery.py`)
The "radar" for finding other users on the network.

- **Broadcasting**: A dedicated thread sends UDP broadcast packets every 5 seconds, containing the user’s name, local IP address, and public key.
- **Listening**: A separate thread listens on a specific UDP port for broadcast packets from other users.
- **Peer Management**: Discovered users are added to a dynamic list of online peers. Users who haven’t broadcasted recently are timed out and removed.

### 3. The Network Core (`network_core.py`)
The "telephone" for reliable communication.

- **TCP Server**: A thread runs a TCP server that listens for incoming connections (for messages or, in the future, files).
- **Connection Handling**: When a peer connects, a new thread handles the connection, decrypts incoming data using the user’s private key, and passes messages to the GUI.
- **TCP Client**: When sending a message, this module encrypts the message with the recipient’s public key, establishes a direct TCP connection, and sends the data.

### 4. The Graphical User Interface (`gui_app.py`)
The user-facing interface.

- Coordinates backend services (discovery and network cores).
- Periodically updates the sidebar with the list of online users from the discovery service.
- Provides an intuitive interface for selecting a user, typing messages, and displaying decrypted conversations.
- Uses a thread-safe queue to receive messages from networking threads and safely update the GUI, preventing crashes.

## Project Structure

```
/Simple-LAN-Chat
|-- gui_app.py             # Main application file, runs the GUI
|-- network_core.py        # Handles all TCP communication (chat/files)
|-- discovery.py           # Handles UDP-based peer discovery
|-- crypto_utils.py        # Manages key generation and encryption/decryption
|-- .gitignore             # Ignores sensitive/generated files
|-- README.md              # This file
|
|-- keys/                  # (Auto-generated) Stores user’s private/public keys
|   |-- private_key.pem
|   `-- public_key.pem
|
`-- received_files/        # (Auto-generated) Stores received files
    `-- sender_username/
        `-- received_file.ext
```

## Setup and Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repository-url>
   cd Simple-LAN-Chat
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install required libraries**:
   ```bash
   pip install customtkinter cryptography
   ```

## How to Run

1. Ensure all users are connected to the same Wi-Fi or local network.
2. Run the main application:
   ```bash
   python gui_app.py
   ```
3. On first launch, the application generates a unique RSA key pair, saved in the `keys/` folder.
4. Enter a username and start chatting securely!

## Future Goals

- [ ] Re-implement secure, end-to-end encrypted file transfers.
- [ ] Add visual indicators for message delivery status (e.g., "Sent," "Delivered").
- [ ] Allow users to set a custom profile picture.
- [ ] Package the application into a standalone executable for easy distribution.

## Contributing

Contributions are welcome! Please fork the repository, create a feature branch, and submit a pull request. Ensure your code follows the project’s style and includes appropriate tests.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.