# Decentralized Local Messenger

**Project Status: In Development**

## Overview

The **Decentralized Local Messenger** is a zero-configuration, serverless messenger and file-sharing application designed to operate entirely on a local network. This project eliminates the dependency on internet connectivity and central servers, enabling fast, private, and robust communication for users on the same Wi-Fi network.

### Project Goal & Motivation

The goal is to create a seamless communication and file-sharing tool that leverages the high-speed capabilities of local networks, bypassing the "Internet-First Trap" where data is unnecessarily routed through distant servers. This application is particularly valuable in offline or network-constrained environments, such as:

- Collaborative workspaces without internet access.
- Secure, private communication within a local network.
- Scenarios requiring high-speed, low-latency data exchange (e.g., file sharing in a classroom or office).

By operating without servers or internet dependency, this tool ensures privacy and functionality even during internet outages.

## Current Progress: Foundational Components

The project currently consists of foundational components built in Python to demonstrate core network programming concepts. These components serve as the building blocks for the final application.

### 1. One-Way Communication (`sender.py` & `receiver.py`)

**Purpose**: Master the basics of network communication.

**Functionality**:
- `sender.py` sends a single "Hello, World!" UDP packet to `receiver.py`.
- `receiver.py` listens for the packet, prints it, and both programs exit.

**Concepts Learned**:
- Creating and closing UDP sockets (`socket.socket`).
- Binding a socket to a specific port (`socket.bind`).
- Sending and receiving data (`socket.sendto`, `socket.recvfrom`).
- Encoding/decoding strings to bytes for network transmission.

### 2. Two-Way Real-Time Chat (`walkie_talkie.py`)

**Purpose**: Build a persistent, real-time, two-way communication channel.

**Functionality**:
- A command-line chat program enabling continuous conversation between two users.
- Limitation: Users must manually know each other's IP address and port.

**Concepts Learned**:
- Using infinite loops (`while True`) to maintain active network services.
- Multi-threading with Python’s `threading` library to handle simultaneous tasks (listening for messages and accepting keyboard input).
- Core principles of responsive network applications.

### 3. Automatic Peer Discovery (`discovery.py`)

**Purpose**: Enable zero-configuration by automatically discovering peers on the local network.

**Functionality**:
- A standalone service that detects other users running the application on the same Wi-Fi network.
- Displays a continuously updated list of online users and their local IP addresses.

**Concepts Learned**:
- UDP Broadcasting to send packets to all devices on the local network using a broadcast address (`<broadcast>` or `255.255.255.255`).
- Socket options (`SO_BROADCAST` for broadcasting, `SO_REUSEADDR` for testing multiple instances on the same port).
- Building a robust, multi-threaded service with dedicated "Broadcaster" and "Listener" threads.

## How to Run the Current Version

The most advanced component is the `discovery.py` service. Follow these steps to test it:

### Prerequisites
- Python 3 installed.
- All devices must be connected to the same Wi-Fi network.

### Steps
1. **Run the script**:
   - Open a terminal and navigate to the project directory.
   - Execute:
     ```bash
     python discovery.py
     ```
2. **Enter a username**:
   - When prompted, type your username and press Enter.
3. **Discover peers**:
   - As other users on the same network run the script, their usernames and IP addresses will automatically appear in your terminal.

## Next Steps

The foundational components are complete, and the next phase involves integrating them into a cohesive application. Planned tasks include:

1. **Integrate Discovery and Communication**:
   - Combine `discovery.py` with a new communication module.
   - Allow users to select a peer from the discovered list to initiate a chat or file transfer.

2. **Switch to TCP for Reliability**:
   - Use TCP sockets for chat and file-sharing to ensure reliable, error-checked data transfer (unlike UDP, which may lose packets).

3. **Build the Main Application Loop**:
   - Develop `main.py` to unify all components.
   - Provide a user-friendly interface to view online users, select a peer, and start a chat or file transfer.

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```bash
   cd decentralized-local-messenger
   ```
3. Ensure Python 3 is installed:
   ```bash
   python --version
   ```
4. Run the desired script (e.g., `Discovery.py`) as described above.

## Contributing

Contributions are welcome! To contribute:
1. Fork the repository.
2. Create a new branch for your feature or bug fix:
   ```bash
   git checkout -b feature-name
   ```
3. Commit your changes and push to your fork.
4. Submit a pull request with a clear description of your changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Contact

For questions or feedback, please open an issue on the repository or contact the project maintainers.

---

*This README will be updated as the project progresses toward the final integrated application.*