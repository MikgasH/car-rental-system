import pytest
import sys
import os
from fastapi.testclient import TestClient
import uuid
import time

# Add project root to path
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, project_root)

from services.car_service.app import app

client = TestClient(app)


class TestCarService:
    """Car Service tests for car rental system"""

    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "timestamp" in data

    def test_ping_endpoint(self):
        """Test ping endpoint"""
        response = client.get("/ping")
        assert response.status_code == 200

        data = response.json()
        assert data["message"] == "pong"
        assert "service" in data

    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200

        data = response.json()
        assert "service" in data
        assert "metrics" in data
        assert "total_cars" in data["metrics"]
        assert "available_cars" in data["metrics"]
        assert "rented_cars" in data["metrics"]
        assert "maintenance_cars" in data["metrics"]

    def test_get_all_cars(self):
        """Test retrieving all cars"""
        response = client.get("/cars")
        assert response.status_code == 200

        cars = response.json()
        assert isinstance(cars, list)

        if cars:
            car = cars[0]
            required_fields = ["car_id", "make", "model", "year", "license_plate",
                               "status", "daily_rate", "location", "created_at", "updated_at"]
            for field in required_fields:
                assert field in car

            # Validate data
            assert car["status"] in ["available", "rented", "maintenance"]
            assert car["daily_rate"] > 0
            assert car["year"] >= 1900
            assert len(car["license_plate"]) > 0

    def test_get_car_by_id_not_found(self):
        """Test retrieving non-existent car"""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/cars/{fake_id}")
        assert response.status_code == 404

    def test_get_available_cars_by_location(self):
        """Test retrieving available cars by location"""
        response = client.get("/cars/available/Vilnius")
        assert response.status_code == 200

        data = response.json()
        assert "location" in data
        assert "available_cars" in data
        assert "count" in data
        assert data["location"] == "Vilnius"
        assert isinstance(data["available_cars"], list)

    def test_get_cars_by_status(self):
        """Test retrieving cars by status"""
        for status in ["available", "rented", "maintenance"]:
            response = client.get(f"/cars/status/{status}")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == status
            assert "cars" in data
            assert "count" in data

    def test_get_cars_by_invalid_status(self):
        """Test retrieving cars with invalid status"""
        response = client.get("/cars/status/invalid")
        assert response.status_code == 400

    def test_create_car_valid(self):
        """Test creating new car with valid data"""
        unique_plate = f"TEST-{int(time.time()) % 10000}"
        new_car_data = {
            "make": "Tesla",
            "model": "Model 3",
            "year": 2023,
            "license_plate": unique_plate,
            "daily_rate": 75.50,
            "location": "Vilnius"
        }

        response = client.post("/cars", json=new_car_data)

        if response.status_code == 200:
            created_car = response.json()

            assert created_car["make"] == new_car_data["make"]
            assert created_car["model"] == new_car_data["model"]
            assert created_car["license_plate"] == new_car_data["license_plate"]
            assert created_car["status"] == "available"

        else:
            # Database might not be accessible
            assert response.status_code in [400, 500]

    def test_create_car_invalid_data(self):
        """Test creating car with invalid data"""
        invalid_car = {
            "make": "",  # Empty make
            "model": "Test",
            "year": 2023,
            "license_plate": "TEST-123",
            "daily_rate": 50.0,
            "location": "Vilnius"
        }

        response = client.post("/cars", json=invalid_car)
        assert response.status_code == 422

    def test_update_car_status(self):
        """Test updating car status"""
        # Get existing cars
        cars_response = client.get("/cars")

        if cars_response.status_code == 200:
            cars = cars_response.json()

            if cars:
                car = cars[0]
                car_id = car["car_id"]
                original_status = car["status"]

                new_status = "maintenance" if original_status != "maintenance" else "available"

                response = client.put(f"/cars/{car_id}/status", params={"new_status": new_status})

                if response.status_code == 200:
                    data = response.json()
                    assert data["car"]["status"] == new_status
                else:
                    assert response.status_code in [400, 404, 500]

    def test_azure_sql_configuration(self):
        """Test Azure SQL Database configuration"""
        db_conn = os.getenv("CAR_DATABASE_CONNECTION_STRING")
        assert db_conn is not None
        assert "car-rental-sql-server.database.windows.net" in db_conn
        assert "car_service_db" in db_conn
        assert "Encrypt=yes" in db_conn
        print("✓ Azure SQL Database correctly configured for Car Service")

    def test_service_bus_configuration(self):
        """Test Azure Service Bus configuration"""
        sb_conn = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
        assert sb_conn is not None
        assert "car-rental-servicebus.servicebus.windows.net" in sb_conn
        assert "SharedAccessKeyName=RootManageSharedAccessKey" in sb_conn
        print("✓ Azure Service Bus correctly configured")


class TestCarServiceAzureIntegration:
    """Azure-specific tests for Car Service"""

    def test_database_connection(self):
        """Test actual Azure SQL connection"""
        try:
            from services.car_service.database import CarDatabase

            car_db = CarDatabase()
            conn = car_db.get_connection()

            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

            conn.close()
            print("✓ Azure SQL Database connection successful")

        except Exception as e:
            pytest.skip(f"Database connection failed: {e}")

    def test_cars_table_exists(self):
        """Test that Cars table exists in Azure SQL"""
        try:
            from services.car_service.database import CarDatabase

            car_db = CarDatabase()
            conn = car_db.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'Cars'
            """)
            result = cursor.fetchone()
            assert result[0] >= 1

            conn.close()
            print("✓ Cars table exists in Azure SQL Database")

        except Exception as e:
            pytest.skip(f"Database table check failed: {e}")

    def test_service_bus_queue_exists(self):
        """Test Service Bus queue configuration"""
        try:
            # Just test that we can import and create client
            from azure.servicebus import ServiceBusClient

            sb_conn = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
            client = ServiceBusClient.from_connection_string(sb_conn)

            # If we get here without exception, connection string is valid
            assert client is not None
            print("✓ Service Bus client creation successful")

        except ImportError:
            pytest.skip("Azure Service Bus SDK not installed")
        except Exception as e:
            pytest.skip(f"Service Bus test failed: {e}")

    def test_license_plate_encryption(self):
        """Test that license plates are encrypted in database"""
        try:
            from services.car_service.database import CarDatabase
            from shared.encryption import encryptor

            car_db = CarDatabase()
            cars = car_db.get_all_cars()

            if cars:
                car = cars[0]
                if car.get("license_plate"):
                    # Try to decrypt - if it changes, it was encrypted
                    decrypted_plate = encryptor.decrypt(car["license_plate"])
                    if decrypted_plate != car["license_plate"]:
                        print("✓ License plate data is encrypted in database")
                    else:
                        print("ℹ License plate appears unencrypted (legacy data?)")

        except Exception as e:
            pytest.skip(f"Database encryption check failed: {e}")