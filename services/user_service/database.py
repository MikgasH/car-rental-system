# services/user_service/database.py
import os
import pyodbc
import uuid
from datetime import datetime
from typing import List, Dict, Optional
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.encryption import encryptor # Теперь PII_FIELDS здесь не нужен, так как app.py делает encrypt_dict/decrypt_dict


class UserDatabase:
    def __init__(self):
        """Initialize user database connection"""
        self.connection_string = os.getenv("USER_DATABASE_CONNECTION_STRING")
        if not self.connection_string:
            raise ValueError("USER_DATABASE_CONNECTION_STRING environment variable not set or is empty.")

    def get_connection(self):
        """Get database connection"""
        return pyodbc.connect(self.connection_string, timeout=30)

    def get_all_users(self) -> List[Dict]:
        """Get all users with encrypted PII data (as stored in DB)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, email, first_name, last_name, phone, created_at, updated_at
            FROM Users
            ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()
        users = []
        for row in rows:
            users.append({
                "user_id": str(row.user_id),
                "email": row.email,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "phone": row.phone,
                # "address": row.address, # <-- УДАЛЕНО
                "created_at": row.created_at,
                "updated_at": row.updated_at
            })
        conn.close()
        return users

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID with encrypted PII data (as stored in DB)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, email, first_name, last_name, phone, created_at, updated_at
            FROM Users
            WHERE user_id = ?
        """, (user_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "user_id": str(row.user_id),
                "email": row.email,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "phone": row.phone,
                # "address": row.address, # <-- УДАЛЕНО
                "created_at": row.created_at,
                "updated_at": row.updated_at
            }
        return None

    def create_user(self, user_data: Dict) -> Dict:
        """Create user with encrypted PII data"""
        conn = self.get_connection()
        cursor = conn.cursor()

        new_user_id = user_data.get("user_id", str(uuid.uuid4()))
        cursor.execute("""
            INSERT INTO Users (user_id, email, first_name, last_name, phone, password_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            new_user_id,
            user_data["email"],
            user_data["first_name"],
            user_data["last_name"],
            user_data["phone"],
            # user_data["address"], # <-- УДАЛЕНО
            user_data.get("password_hash", "temp_hash_123")
        ))

        conn.commit()
        conn.close()

        return self.get_user_by_id(new_user_id)

    def update_user(self, user_id: str, update_data: Dict) -> bool:
        """Update user with encrypted PII data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            query = """
                UPDATE Users
                SET email = ?, first_name = ?, last_name = ?, phone = ?, updated_at = GETUTCDATE() -- <-- УДАЛЕНО 'address'
                WHERE user_id = ?
            """
            cursor.execute(query,
                           update_data["email"],
                           update_data["first_name"],
                           update_data["last_name"],
                           update_data["phone"],
                           # update_data["address"], # <-- УДАЛЕНО
                           user_id)
            conn.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()
            conn.close()


    def search_users_by_email(self, email_query: str) -> List[Dict]:
        """Search users by email - note: this requires decrypting all emails"""
        all_users = self.get_all_users()
        matching_users = []

        for user_data_from_db in all_users:
            # PII_FIELDS должен быть доступен здесь для decrypt_dict
            # Предполагаем, что он импортируется из shared.encryption
            from shared.encryption import PII_FIELDS # <-- Если не импортируется в начале файла

            decrypted_user = encryptor.decrypt_dict(user_data_from_db, PII_FIELDS['users'])
            if email_query.lower() in decrypted_user["email"].lower():
                matching_users.append(decrypted_user)

        return matching_users