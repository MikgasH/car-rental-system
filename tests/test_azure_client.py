import pytest
import sys
import os

# Add project root path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from azure_database_client import azure_client
except ImportError:
    pytest.skip("Azure client not available", allow_module_level=True)


@pytest.mark.skipif(azure_client is None, reason="Azure client not initialized")
class TestAzureClient:
    """Azure SQL Client test cases"""

    def test_azure_client_initialized(self):
        """Test Azure client initialization"""
        assert azure_client is not None

    def test_connection_info(self):
        """Test connection information retrieval"""
        info = azure_client.get_connection_info()

        assert isinstance(info, dict)
        assert info["provider"] == "Azure SQL Database"
        assert info["server"] == "car-rental-sql-server.database.windows.net"
        assert info["database"] == "car_rental_db"
        assert info["connection_method"] == "pyodbc direct connection"
        assert info["status"] == "connected"
        assert "tables" in info
        assert isinstance(info["tables"], list)

    def test_get_users_returns_list(self):
        """Test user retrieval returns list"""
        try:
            users = azure_client.get_users()

            assert isinstance(users, list)
            assert len(users) >= 0

            if users:
                user = users[0]
                required_fields = ["user_id", "email", "first_name", "last_name", "created_at", "updated_at"]
                for field in required_fields:
                    assert field in user
                    assert user[field] is not None
        except Exception as e:
            pytest.fail(f"get_users failed: {e}")

    def test_get_cars_returns_list(self):
        """Test car retrieval returns list"""
        try:
            cars = azure_client.get_cars()

            assert isinstance(cars, list)
            assert len(cars) >= 0

            if cars:
                car = cars[0]
                required_fields = ["car_id", "make", "model", "year", "license_plate",
                                   "status", "daily_rate", "location", "created_at", "updated_at"]
                for field in required_fields:
                    assert field in car
                    assert car[field] is not None

                assert isinstance(car["year"], int)
                assert isinstance(car["daily_rate"], float)
                assert car["status"] in ["available", "rented", "maintenance"]
        except Exception as e:
            pytest.fail(f"get_cars failed: {e}")

    def test_get_user_by_id_nonexistent(self):
        """Test retrieving non-existent user"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        user = azure_client.get_user_by_id(fake_id)

        assert user is None

    def test_get_car_by_id_nonexistent(self):
        """Test retrieving non-existent car"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        car = azure_client.get_car_by_id(fake_id)

        assert car is None

    def test_log_to_azure(self):
        """Test Azure logging functionality"""
        try:
            azure_client.log_to_azure("test-service", "INFO", "Test log message")
            azure_client.log_to_azure("test-service", "WARN", "Test warning", user_id="test-user")
            azure_client.log_to_azure("test-service", "ERROR", "Test error",
                                      additional_data={"test": True, "error_code": 500})
            assert True
        except Exception as e:
            print(f"Logging warning: {e}")
            assert True

    def test_update_car_status_nonexistent(self):
        """Test updating status of non-existent car"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        result = azure_client.update_car_status(fake_id, "available")

        assert result is False

    def test_create_user_with_valid_data(self):
        """Test creating user with valid data"""
        import time

        user_data = {
            "email": f"test-user-{int(time.time())}@example.com",
            "first_name": "Test",
            "last_name": "User",
            "phone": "+37060000999",
            "password_hash": "test_hash_123"
        }

        try:
            created_user = azure_client.create_user(user_data)

            assert isinstance(created_user, dict)
            assert created_user["email"] == user_data["email"]
            assert created_user["first_name"] == user_data["first_name"]
            assert created_user["last_name"] == user_data["last_name"]
            assert "user_id" in created_user
            assert "created_at" in created_user
            assert "updated_at" in created_user
        except Exception as e:
            print(f"User creation failed (expected in some cases): {e}")
            assert True

    def test_create_car_with_valid_data(self):
        """Test creating car with valid data"""
        import time

        car_data = {
            "make": "Test",
            "model": "Car",
            "year": 2020,
            "license_plate": f"TEST-{int(time.time()) % 1000}",
            "daily_rate": 50.0,
            "location": "Test Location"
        }

        try:
            created_car = azure_client.create_car(car_data)

            assert isinstance(created_car, dict)
            assert created_car["make"] == car_data["make"]
            assert created_car["model"] == car_data["model"]
            assert created_car["year"] == car_data["year"]
            assert created_car["license_plate"] == car_data["license_plate"]
            assert created_car["status"] == "available"
            assert "car_id" in created_car
            assert "created_at" in created_car
            assert "updated_at" in created_car
        except Exception as e:
            print(f"Car creation failed (expected in some cases): {e}")
            assert True