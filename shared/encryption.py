from cryptography.fernet import Fernet
import os
import base64


class DataEncryption:
    """Class for encrypting and decrypting PII data"""

    def __init__(self):
        """Initialize encryption with key from environment or generate new one"""
        encryption_key = os.getenv("ENCRYPTION_KEY")

        if not encryption_key:
            encryption_key = Fernet.generate_key().decode()
            print(f"WARNING: No ENCRYPTION_KEY found in environment variables!")
            print(f"Generated new encryption key: {encryption_key}")
            print(f"Add this to your .env file: ENCRYPTION_KEY={encryption_key}")
        else:
            encryption_key = encryption_key.encode()

        self.cipher = Fernet(encryption_key)

    def encrypt(self, data: str) -> str:
        """Encrypt a string value"""
        if not data:
            return data

        try:
            encrypted_bytes = self.cipher.encrypt(data.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            print(f"Encryption error: {e}")
            return data

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt an encrypted string value"""
        if not encrypted_data:
            return encrypted_data

        try:
            decrypted_bytes = self.cipher.decrypt(encrypted_data.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            print(f"Decryption warning: {e}")
            return encrypted_data

    def encrypt_dict(self, data: dict, fields: list) -> dict:
        """Encrypt specific fields in a dictionary"""
        encrypted_data = data.copy()
        for field in fields:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self.encrypt(encrypted_data[field])
        return encrypted_data

    def decrypt_dict(self, data: dict, fields: list) -> dict:
        """Decrypt specific fields in a dictionary"""
        decrypted_data = data.copy()
        for field in fields:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_data[field] = self.decrypt(decrypted_data[field])
        return decrypted_data


encryptor = DataEncryption()

PII_FIELDS = {
    'users': ['email', 'first_name', 'last_name', 'phone'],
    'cars': ['license_plate'],
    'rentals': ['pickup_location', 'return_location']
}