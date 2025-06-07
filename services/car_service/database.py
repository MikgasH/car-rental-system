import os
import pyodbc
import uuid
from datetime import datetime
from typing import List, Dict, Optional
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.encryption import encryptor


class CarDatabase:
    def __init__(self):
        """Initialize car database connection"""
        self.connection_string = os.getenv("CAR_DATABASE_CONNECTION_STRING")
        if not self.connection_string:
            raise ValueError("CAR_DATABASE_CONNECTION_STRING environment variable not set or is empty.")

    def get_connection(self):
        """Get database connection"""
        return pyodbc.connect(self.connection_string, timeout=30)

    def get_all_cars(self) -> List[Dict]:
        """Get all cars"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT car_id, make, model, year, license_plate, status, daily_rate, location, created_at, updated_at
            FROM Cars
            ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()
        cars = []
        for row in rows:
            cars.append({
                "car_id": str(row.car_id),
                "make": row.make,
                "model": row.model,
                "year": row.year,
                "license_plate": encryptor.decrypt(row.license_plate),
                "status": row.status,
                "daily_rate": float(row.daily_rate),
                "location": row.location,
                "created_at": row.created_at,
                "updated_at": row.updated_at
            })
        conn.close()
        return cars

    def get_car_by_id(self, car_id: str) -> Optional[Dict]:
        """Get car by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT car_id, make, model, year, license_plate, status, daily_rate, location, created_at, updated_at
            FROM Cars
            WHERE car_id = ?
        """, (car_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "car_id": str(row.car_id),
                "make": row.make,
                "model": row.model,
                "year": row.year,
                "license_plate": encryptor.decrypt(row.license_plate),
                "status": row.status,
                "daily_rate": float(row.daily_rate),
                "location": row.location,
                "created_at": row.created_at,
                "updated_at": row.updated_at
            }
        return None

    def update_car_status(self, car_id: str, new_status: str) -> bool:
        """Update car status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Cars 
            SET status = ?, updated_at = GETUTCDATE()
            WHERE car_id = ?
        """, (new_status, car_id))

        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()

        return rows_affected > 0

    def create_car(self, car_data: Dict) -> Dict:
        """Create car"""
        conn = self.get_connection()
        cursor = conn.cursor()

        new_car_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO Cars (car_id, make, model, year, license_plate, daily_rate, location)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            new_car_id,
            car_data["make"],
            car_data["model"],
            car_data["year"],
            encryptor.encrypt(car_data["license_plate"]),
            car_data["daily_rate"],
            car_data["location"]
        ))

        conn.commit()
        conn.close()

        return self.get_car_by_id(new_car_id)

    def check_duplicate_license_plate(self, license_plate: str) -> bool:
        """Check if license plate already exists"""
        all_cars = self.get_all_cars()
        for car in all_cars:
            if car["license_plate"] == license_plate:
                return True
        return False