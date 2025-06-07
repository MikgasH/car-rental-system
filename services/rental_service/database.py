import os
import pyodbc
import uuid
import requests
from datetime import datetime
from typing import List, Dict, Optional
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.encryption import encryptor


class RentalDatabase:
    def __init__(self):
        """Initialize rental database connection"""
        self.connection_string = os.getenv("RENTAL_DATABASE_CONNECTION_STRING")
        if not self.connection_string:
            raise ValueError("RENTAL_DATABASE_CONNECTION_STRING environment variable not set or is empty.")

        self.user_service_url = os.getenv("USER_SERVICE_URL", "http://localhost:5001")
        self.car_service_url = os.getenv("CAR_SERVICE_URL", "http://localhost:5002")

    def get_connection(self):
        """Get database connection"""
        return pyodbc.connect(self.connection_string, timeout=30)

    def get_all_rentals(self) -> List[Dict]:
        """Get all rentals"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rental_id, user_id, car_id, start_date, end_date, 
                   total_amount, status, pickup_location, return_location, 
                   created_at, updated_at
            FROM Rentals 
            ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()
        rentals = []
        for row in rows:
            rentals.append({
                "rental_id": str(row.rental_id),
                "user_id": str(row.user_id),
                "car_id": str(row.car_id),
                "start_date": row.start_date,
                "end_date": row.end_date,
                "total_amount": float(row.total_amount),
                "status": row.status,
                "pickup_location": encryptor.decrypt(row.pickup_location),
                "return_location": encryptor.decrypt(row.return_location),
                "created_at": row.created_at,
                "updated_at": row.updated_at
            })
        conn.close()
        return rentals

    def get_rental_by_id(self, rental_id: str) -> Optional[Dict]:
        """Get rental by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rental_id, user_id, car_id, start_date, end_date, 
                   total_amount, status, pickup_location, return_location, 
                   created_at, updated_at
            FROM Rentals 
            WHERE rental_id = ?
        """, (rental_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "rental_id": str(row.rental_id),
                "user_id": str(row.user_id),
                "car_id": str(row.car_id),
                "start_date": row.start_date,
                "end_date": row.end_date,
                "total_amount": float(row.total_amount),
                "status": row.status,
                "pickup_location": encryptor.decrypt(row.pickup_location),
                "return_location": encryptor.decrypt(row.return_location),
                "created_at": row.created_at,
                "updated_at": row.updated_at
            }
        return None

    def create_rental(self, rental_data: Dict) -> Dict:
        """Create rental"""
        conn = self.get_connection()
        cursor = conn.cursor()

        new_rental_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO Rentals (
                rental_id, user_id, car_id, start_date, end_date,
                total_amount, status, pickup_location, return_location
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            new_rental_id,
            rental_data["user_id"],
            rental_data["car_id"],
            rental_data["start_date"],
            rental_data["end_date"],
            rental_data["total_amount"],
            "pending",
            encryptor.encrypt(rental_data["pickup_location"]),
            encryptor.encrypt(rental_data["return_location"])
        ))

        conn.commit()
        conn.close()

        return self.get_rental_by_id(new_rental_id)

    def get_user_info(self, user_id: str) -> Optional[Dict]:
        """Get user information from User Service"""
        try:
            response = requests.get(f"{self.user_service_url}/users/{user_id}")
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None

    def get_car_info(self, car_id: str) -> Optional[Dict]:
        """Get car information from Car Service"""
        try:
            response = requests.get(f"{self.car_service_url}/cars/{car_id}")
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None

    def update_rental_status(self, rental_id: str, new_status: str) -> bool:
        """Update rental status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Rentals 
            SET status = ?, updated_at = GETUTCDATE()
            WHERE rental_id = ?
        """, (new_status, rental_id))

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        return rows_affected > 0