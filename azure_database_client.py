import os
import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional
from dotenv import load_dotenv

try:
    import pyodbc
    SQL_AVAILABLE = True
except ImportError:
    print("Error: pyodbc not installed. Run: pip install pyodbc")
    SQL_AVAILABLE = False

load_dotenv()

class AzureSQLClient:
    """Azure SQL Database client using direct pyodbc connection"""

    def __init__(self):
        self.connection_string = os.getenv("DATABASE_CONNECTION_STRING")
        self.connection = None

        if not self.connection_string:
            raise ValueError("DATABASE_CONNECTION_STRING not found in .env file")

        if not SQL_AVAILABLE:
            raise ImportError("pyodbc not available")

        self._initialize_connection()

    def _initialize_connection(self):
        """Initialize connection to Azure SQL"""
        try:
            # Test connection
            conn = pyodbc.connect(self.connection_string, timeout=30)
            cursor = conn.cursor()

            cursor.execute("SELECT 1 as test")
            test_result = cursor.fetchone()

            if test_result and test_result[0] == 1:
                print("Connected to Azure SQL Database")
                self._check_existing_tables(cursor)
                conn.close()
            else:
                raise Exception("Connection test failed")

        except Exception as e:
            print(f"Azure SQL connection error: {e}")
            raise

    def _get_connection(self):
        """Get new connection for each request"""
        try:
            return pyodbc.connect(self.connection_string, timeout=30)
        except Exception as e:
            print(f"Connection error: {e}")
            raise

    def _check_existing_tables(self, cursor):
        """Check existing tables"""
        try:
            cursor.execute("""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
            """)

            tables = cursor.fetchall()

            for table in tables:
                table_name = table[0]
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                    count = cursor.fetchone()[0]
                    print(f"Table {table_name}: {count} records")
                except Exception:
                    pass

        except Exception as e:
            print(f"Table check error: {e}")

    def log_to_azure(self, service_name: str, level: str, message: str,
                    user_id: str = None, additional_data: dict = None):
        """Log to Azure SQL Application_Logs table"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Check if Application_Logs table exists
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'Application_Logs'
            """)

            table_exists = cursor.fetchone()[0] > 0

            if table_exists:
                cursor.execute("""
                    INSERT INTO Application_Logs (service_name, level, message, user_id, additional_data)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    service_name,
                    level.upper(),
                    message,
                    user_id,
                    json.dumps(additional_data) if additional_data else None
                ))
                conn.commit()

            conn.close()

        except Exception as e:
            pass

    def get_users(self) -> List[Dict]:
        """Get all users from Azure SQL"""
        try:
            conn = self._get_connection()
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
                    "created_at": row.created_at,
                    "updated_at": row.updated_at
                })

            conn.close()
            self.log_to_azure("azure-client", "INFO", f"Retrieved {len(users)} users")
            return users

        except Exception as e:
            self.log_to_azure("azure-client", "ERROR", f"Failed to get users: {e}")
            raise

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID from Azure SQL"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT user_id, email, first_name, last_name, phone, created_at, updated_at
                FROM Users
                WHERE user_id = ?
            """, (user_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                user = {
                    "user_id": str(row.user_id),
                    "email": row.email,
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                    "phone": row.phone,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at
                }
                self.log_to_azure("azure-client", "INFO", f"Found user {user_id}")
                return user

            return None

        except Exception as e:
            self.log_to_azure("azure-client", "ERROR", f"Failed to get user {user_id}: {e}")
            raise

    def get_cars(self) -> List[Dict]:
        """Get all cars from Azure SQL"""
        try:
            conn = self._get_connection()
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
                    "license_plate": row.license_plate,
                    "status": row.status,
                    "daily_rate": float(row.daily_rate),
                    "location": row.location,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at
                })

            conn.close()
            self.log_to_azure("azure-client", "INFO", f"Retrieved {len(cars)} cars")
            return cars

        except Exception as e:
            self.log_to_azure("azure-client", "ERROR", f"Failed to get cars: {e}")
            raise

    def get_car_by_id(self, car_id: str) -> Optional[Dict]:
        """Get car by ID from Azure SQL"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT car_id, make, model, year, license_plate, status, daily_rate, location, created_at, updated_at
                FROM Cars
                WHERE car_id = ?
            """, (car_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                car = {
                    "car_id": str(row.car_id),
                    "make": row.make,
                    "model": row.model,
                    "year": row.year,
                    "license_plate": row.license_plate,
                    "status": row.status,
                    "daily_rate": float(row.daily_rate),
                    "location": row.location,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at
                }
                self.log_to_azure("azure-client", "INFO", f"Found car {car_id}")
                return car

            return None

        except Exception as e:
            self.log_to_azure("azure-client", "ERROR", f"Failed to get car {car_id}: {e}")
            raise

    def update_car_status(self, car_id: str, new_status: str) -> bool:
        """Update car status in Azure SQL"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE Cars 
                SET status = ?, updated_at = GETUTCDATE()
                WHERE car_id = ?
            """, (new_status, car_id))

            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()

            if rows_affected > 0:
                self.log_to_azure("azure-client", "INFO", f"Updated car {car_id} status to {new_status}")
                return True
            else:
                self.log_to_azure("azure-client", "WARN", f"Car {car_id} not found for status update")
                return False

        except Exception as e:
            self.log_to_azure("azure-client", "ERROR", f"Failed to update car {car_id} status: {e}")
            return False

    def create_user(self, user_data: Dict) -> Dict:
        """Create user in Azure SQL"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            new_user_id = str(uuid.uuid4())

            cursor.execute("""
                INSERT INTO Users (user_id, email, first_name, last_name, phone, password_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                new_user_id,
                user_data["email"],
                user_data["first_name"],
                user_data["last_name"],
                user_data.get("phone"),
                user_data.get("password_hash", "temp_hash_123")
            ))

            # Get created user
            cursor.execute("""
                SELECT user_id, email, first_name, last_name, phone, created_at, updated_at
                FROM Users
                WHERE user_id = ?
            """, (new_user_id,))

            row = cursor.fetchone()
            conn.commit()
            conn.close()

            if row:
                created_user = {
                    "user_id": str(row.user_id),
                    "email": row.email,
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                    "phone": row.phone,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at
                }

                self.log_to_azure("azure-client", "INFO", f"Created user {created_user['user_id']}")
                return created_user
            else:
                raise Exception("Failed to retrieve created user")

        except Exception as e:
            self.log_to_azure("azure-client", "ERROR", f"Failed to create user: {e}")
            raise

    def create_car(self, car_data: Dict) -> Dict:
        """Create car in Azure SQL"""
        try:
            conn = self._get_connection()
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
                car_data["license_plate"],
                car_data["daily_rate"],
                car_data["location"]
            ))

            # Get created car
            cursor.execute("""
                SELECT car_id, make, model, year, license_plate, status, daily_rate, location, created_at, updated_at
                FROM Cars
                WHERE car_id = ?
            """, (new_car_id,))

            row = cursor.fetchone()
            conn.commit()
            conn.close()

            if row:
                created_car = {
                    "car_id": str(row.car_id),
                    "make": row.make,
                    "model": row.model,
                    "year": row.year,
                    "license_plate": row.license_plate,
                    "status": row.status,
                    "daily_rate": float(row.daily_rate),
                    "location": row.location,
                    "created_at": row.created_at,
                    "updated_at": row.updated_at
                }

                self.log_to_azure("azure-client", "INFO", f"Created car {created_car['car_id']}")
                return created_car
            else:
                raise Exception("Failed to retrieve created car")

        except Exception as e:
            self.log_to_azure("azure-client", "ERROR", f"Failed to create car: {e}")
            raise

    def get_connection_info(self) -> Dict:
        """Get Azure connection information"""
        return {
            "provider": "Azure SQL Database",
            "server": "car-rental-sql-server.database.windows.net",
            "database": "car_rental_db",
            "connection_method": "pyodbc direct connection",
            "status": "connected",
            "tables": ["Users", "Cars", "Rentals", "Payments", "Application_Logs"]
        }

try:
    azure_client = AzureSQLClient()
except Exception as e:
    print(f"Failed to initialize Azure SQL client: {e}")
    azure_client = None

def test_azure_connection():
    """Test Azure SQL connection"""
    if not azure_client:
        print("Azure client not initialized")
        return False

    try:
        print("Testing Azure SQL connection...")

        users = azure_client.get_users()
        print(f"Users in database: {len(users)}")

        cars = azure_client.get_cars()
        print(f"Cars in database: {len(cars)}")

        azure_client.log_to_azure("system-test", "INFO", "Connection test completed")

        print("Azure SQL connection test successful")
        return True

    except Exception as e:
        print(f"Connection test failed: {e}")
        return False

if __name__ == "__main__":
    test_azure_connection()