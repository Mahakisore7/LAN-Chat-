# crypto_utils.py

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os

KEYS_DIR = "keys"
PRIVATE_KEY_FILE = os.path.join(KEYS_DIR, "private_key.pem")
PUBLIC_KEY_FILE = os.path.join(KEYS_DIR, "public_key.pem")

# --- RSA Key Generation and Management (for messages and key exchange) ---

def generate_and_save_keys():
    """Generates a new RSA key pair if they don't exist, else loads them."""
    if os.path.exists(PRIVATE_KEY_FILE) and os.path.exists(PUBLIC_KEY_FILE):
        return load_public_key(), load_private_key()

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    os.makedirs(KEYS_DIR, exist_ok=True)

    with open(PRIVATE_KEY_FILE, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))
    with open(PUBLIC_KEY_FILE, "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))
    return public_key, private_key

def load_public_key():
    with open(PUBLIC_KEY_FILE, "rb") as f:
        return serialization.load_pem_public_key(f.read())

def load_private_key():
    with open(PRIVATE_KEY_FILE, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)

def public_key_to_string(public_key):
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode('utf-8')

def string_to_public_key(key_string):
    return serialization.load_pem_public_key(key_string.encode('utf-8'))

# --- RSA Encryption/Decryption (for small data like messages and AES keys) ---

def encrypt_with_rsa(public_key, data):
    """Encrypts small data using the recipient's public key (RSA)."""
    return public_key.encrypt(
        data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

def decrypt_with_rsa(private_key, encrypted_data):
    """Decrypts small data using the user's own private key (RSA)."""
    return private_key.decrypt(
        encrypted_data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

# --- AES Encryption/Decryption (for large data like files) ---

def generate_aes_key():
    """Generates a new random 256-bit AES key."""
    return os.urandom(32) # AES-256 uses a 32-byte key

def encrypt_file_chunk(aes_key, data):
    """Encrypts a chunk of file data using AES."""
    iv = os.urandom(12)  # Initialization vector, must be unique per encryption
    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(data) + encryptor.finalize()
    return iv + encryptor.tag + encrypted_data # Prepend IV and tag for decryption

def decrypt_file_chunk(aes_key, encrypted_data_with_iv_tag):
    """Decrypts a chunk of file data using AES."""
    iv = encrypted_data_with_iv_tag[:12]
    tag = encrypted_data_with_iv_tag[12:28]
    encrypted_data = encrypted_data_with_iv_tag[28:]
    cipher = Cipher(algorithms.AES(aes_key), modes.GCM(iv, tag), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(encrypted_data) + decryptor.finalize()