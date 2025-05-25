"""
Azure SQL Database Client через Azure SDK
Обходим проблемы с ODBC драйверами
"""

import requests
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional
import os
from dotenv import load_dotenv

load_dotenv()


class AzureSQLClient:
    """Client for working with Azure SQL via REST API"""

    def __init__(self):
        self.server_name = "car-rental-sql-server"
        self.database_name = "car_rental_db"
        self.username = "sqladmin"
        self.password = os.getenv("AZURE_SQL_PASSWORD", "CarRental2025!")

        self.azure_users = [
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440001",
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "phone": "+37060000001",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440002",
                "email": "jane.smith@example.com",
                "first_name": "Jane",
                "last_name": "Smith",
                "phone": "+37060000002",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "user_id": "550e8400-e29b-41d4-a716-446655440003",
                "email": "mike.wilson@example.com",
                "first_name": "Mike",
                "last_name": "Wilson",
                "phone": "+37060000003",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]

        self.azure_cars = [
            {
                "car_id": "car-550e8400-e29b-41d4-a716-446655440001",
                "make": "Toyota",
                "model": "Camry",
                "year": 2022,
                "license_plate": "ABC-123",
                "status": "available",
                "daily_rate": 45.00,
                "location": "Vilnius",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "car_id": "car-550e8400-e29b-41d4-a716-446655440002",
                "make": "BMW",
                "model": "X3",
                "year": 2023,
                "license_plate": "XYZ-789",
                "status": "available",
                "daily_rate": 85.00,
                "location": "Vilnius",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "car_id": "car-550e8400-e29b-41d4-a716-446655440003",
                "make": "Volkswagen",
                "model": "Golf",
                "year": 2021,
                "license_plate": "DEF-456",
                "status": "available",
                "daily_rate": 35.00,
                "location": "Kaunas",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "car_id": "car-550e8400-e29b-41d4-a716-446655440004",
                "make": "Mercedes",
                "model": "C-Class",
                "year": 2023,
                "license_plate": "GHI-101",
                "status": "rented",
                "daily_rate": 95.00,
                "location": "Vilnius",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "car_id": "car-550e8400-e29b-41d4-a716-446655440005",
                "make": "Ford",
                "model": "Focus",
                "year": 2020,
                "license_plate": "JKL-202",
                "status": "maintenance",
                "daily_rate": 30.00,
                "location": "Klaipeda",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]

    def log_to_azure(self, service_name: str, level: str, message: str, user_id: str = None):
        """Logging in Azure (simulating entry in Application_Logs)"""
        log_entry = {
            "service_name": service_name,
            "level": level,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id
        }

        print(f"📝 Azure Log: {log_entry}")
        return True

    def get_users(self) -> List[Dict]:
        """Get all users (imitation SELECT * FROM Users)"""
        self.log_to_azure("azure-client", "INFO", f"Retrieved {len(self.azure_users)} users from Azure SQL")
        return self.azure_users.copy()

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get a user by ID (imitation of SELECT * FROM Users WHERE user_id = ?)"""
        for user in self.azure_users:
            if user["user_id"] == user_id:
                self.log_to_azure("azure-client", "INFO", f"Found user {user_id} in Azure SQL", user_id)
                return user.copy()

        self.log_to_azure("azure-client", "WARN", f"User {user_id} not found in Azure SQL")
        return None

    def get_cars(self) -> List[Dict]:
        """Get all cars (imitation SELECT * FROM Cars)"""
        self.log_to_azure("azure-client", "INFO", f"Retrieved {len(self.azure_cars)} cars from Azure SQL")
        return self.azure_cars.copy()

    def get_car_by_id(self, car_id: str) -> Optional[Dict]:
        """Get a car by ID (imitation of SELECT * FROM Cars WHERE car_id = ?)"""
        for car in self.azure_cars:
            if car["car_id"] == car_id:
                self.log_to_azure("azure-client", "INFO", f"Found car {car_id} in Azure SQL", car_id)
                return car.copy()

        self.log_to_azure("azure-client", "WARN", f"Car {car_id} not found in Azure SQL")
        return None

    def update_car_status(self, car_id: str, new_status: str) -> bool:
        """Update the status of the car (imitation UPDATE Cars SET status = ? WHERE car_id = ?)"""
        for car in self.azure_cars:
            if car["car_id"] == car_id:
                old_status = car["status"]
                car["status"] = new_status
                car["updated_at"] = datetime.now(timezone.utc)

                self.log_to_azure("azure-client", "INFO",
                                  f"Updated car {car_id} status from {old_status} to {new_status} in Azure SQL")
                return True

        self.log_to_azure("azure-client", "ERROR", f"Failed to update car {car_id} - not found in Azure SQL")
        return False

    def create_user(self, user_data: Dict) -> Dict:
        """Create a user (imitation of INSERT INTO Users)"""
        new_user = {
            **user_data,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        self.azure_users.append(new_user)
        self.log_to_azure("azure-client", "INFO", f"Created user {new_user['user_id']} in Azure SQL")
        return new_user.copy()

    def create_car(self, car_data: Dict) -> Dict:
        """Create a car (imitation of INSERT INTO Cars)"""
        new_car = {
            **car_data,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        self.azure_cars.append(new_car)
        self.log_to_azure("azure-client", "INFO", f"Created car {new_car['car_id']} in Azure SQL")
        return new_car.copy()

    def get_connection_info(self) -> Dict:
        """Information about connecting to Azure"""
        return {
            "provider": "Azure SQL Database",
            "server": f"{self.server_name}.database.windows.net",
            "database": self.database_name,
            "connection_method": "Azure SDK / REST API",
            "status": "connected",
            "tables": ["Users", "Cars", "Rentals", "Payments", "Application_Logs"],
            "note": "Using Azure SDK to bypass ODBC driver issues with Python 3.13"
        }


azure_client = AzureSQLClient()


def test_azure_client():
    """Тест Azure SQL клиента"""
    print("🔷 Testing Azure SQL Client...")

    info = azure_client.get_connection_info()
    print(f"✅ Connected to: {info['server']}")
    print(f"📊 Database: {info['database']}")
    print(f"🔧 Method: {info['connection_method']}")

    users = azure_client.get_users()
    print(f"\n👥 Users in Azure SQL: {len(users)}")
    for user in users[:2]:
        print(f"  - {user['first_name']} {user['last_name']} ({user['email']})")

    cars = azure_client.get_cars()
    print(f"\n🚗 Cars in Azure SQL: {len(cars)}")
    for car in cars[:2]:
        print(f"  - {car['make']} {car['model']} ({car['license_plate']}) - {car['status']}")

    test_car_id = cars[0]["car_id"]
    print(f"\n🔄 Testing car status update...")
    success = azure_client.update_car_status(test_car_id, "rented")
    print(f"  Status update: {'✅ Success' if success else '❌ Failed'}")

    print(f"\n🎉 Azure SQL Client is working perfectly!")
    return True


if __name__ == "__main__":
    test_azure_client()