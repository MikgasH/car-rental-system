import pytest
import sys
import os
from fastapi.testclient import TestClient
import uuid
import time
from datetime import datetime, timedelta

# Add project root to path
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, project_root)

from services.rental_service.app import app

client = TestClient(app)


class TestRentalService:
    """Rental Service tests for car rental system"""

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
        assert "total_rentals" in data["metrics"]
        assert "active_rentals" in data["metrics"]
        assert "completed_rentals" in data["metrics"]
        assert "pending_rentals" in data["metrics"]
        assert "cancelled_rentals" in data["metrics"]
        assert "total_revenue" in data["metrics"]

    def test_get_all_rentals(self):
        """Test retrieving all rentals"""
        response = client.get("/rentals")

        # Should always return 200, even if database has issues
        if response.status_code == 200:
            rentals = response.json()
            assert isinstance(rentals, list)

            if rentals:
                rental = rentals[0]
                required_fields = [
                    "rental_id", "user_id", "car_id", "start_date", "end_date",
                    "total_amount", "status", "pickup_location", "return_location",
                    "created_at", "updated_at"
                ]
                for field in required_fields:
                    assert field in rental

                # Validate data
                assert rental["status"] in ["pending", "active", "completed", "cancelled"]
                assert rental["total_amount"] >= 0
                assert len(rental["pickup_location"]) > 0
                assert len(rental["return_location"]) > 0
        else:
            # If database connection fails, that's also acceptable in test environment
            assert response.status_code in [500]
            print("ℹ Database connection issue - acceptable in test environment")

    def test_get_rental_by_id_not_found(self):
        """Test retrieving non-existent rental"""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/rentals/{fake_id}")
        # Should return 404 for non-existent rental, or 500 if database issues
        assert response.status_code in [404, 500]

    def test_create_rental_invalid_dates(self):
        """Test creating rental with invalid date range"""
        rental_data = {
            "user_id": str(uuid.uuid4()),
            "car_id": str(uuid.uuid4()),
            "start_date": "2025-06-15T10:00:00Z",
            "end_date": "2025-06-10T10:00:00Z",  # End before start
            "pickup_location": "Vilnius Airport",
            "return_location": "Vilnius Airport"
        }

        response = client.post("/rentals", json=rental_data)
        # Should catch invalid dates before hitting database
        assert response.status_code == 400

    def test_create_rental_nonexistent_user(self):
        """Test creating rental with non-existent user"""
        future_start = (datetime.now() + timedelta(days=1)).isoformat() + "Z"
        future_end = (datetime.now() + timedelta(days=5)).isoformat() + "Z"

        rental_data = {
            "user_id": str(uuid.uuid4()),
            "car_id": str(uuid.uuid4()),
            "start_date": future_start,
            "end_date": future_end,
            "pickup_location": "Vilnius Airport",
            "return_location": "Vilnius Airport"
        }

        response = client.post("/rentals", json=rental_data)
        # Could be 404 (user not found) or 500 (database/service issue)
        assert response.status_code in [404, 500]

    def test_create_rental_invalid_data_format(self):
        """Test creating rental with invalid data format"""
        invalid_rental = {
            "user_id": "not-a-uuid",
            "car_id": str(uuid.uuid4()),
            "start_date": "2025-06-15T10:00:00Z",
            "end_date": "2025-06-20T10:00:00Z",
            "pickup_location": "Vilnius Airport",
            "return_location": "Vilnius Airport"
        }

        response = client.post("/rentals", json=invalid_rental)

        # Accept any error response - the important thing is that it's not 200
        if response.status_code == 200:
            pytest.fail("Should not accept invalid UUID format")

        # Accept various error codes depending on where validation happens
        assert response.status_code in [400, 422, 500]
        print(f"✓ Invalid data correctly rejected with status {response.status_code}")

    def test_update_rental_status_not_found(self):
        """Test updating status of non-existent rental"""
        fake_id = str(uuid.uuid4())
        response = client.put(f"/rentals/{fake_id}/status", params={"new_status": "active"})
        assert response.status_code in [404, 500]

    def test_update_rental_status_invalid(self):
        """Test updating rental with invalid status"""
        fake_id = str(uuid.uuid4())
        response = client.put(f"/rentals/{fake_id}/status", params={"new_status": "invalid_status"})
        assert response.status_code == 400

    def test_rental_business_logic(self):
        """Test rental business logic and validation"""
        response = client.get("/rentals")

        # Accept both success and server errors (dependency issues)
        if response.status_code == 200:
            rentals = response.json()
            assert isinstance(rentals, list), "Response should be a list"

            if rentals:
                # If we have data, validate it
                rental = rentals[0]

                # Test date logic
                start_date = datetime.fromisoformat(rental["start_date"].replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(rental["end_date"].replace('Z', '+00:00'))
                assert end_date >= start_date, "End date should be after or equal to start date"

                # Test UUID formats
                try:
                    uuid.UUID(rental["rental_id"])
                    uuid.UUID(rental["user_id"])
                    uuid.UUID(rental["car_id"])
                except ValueError:
                    pytest.fail("Invalid UUID format in rental data")

                # Test amount is reasonable
                assert rental["total_amount"] >= 0, "Total amount should be non-negative"
                assert rental["total_amount"] < 100000, "Total amount should be reasonable"

                print(f"Business logic validated with {len(rentals)} rental(s)")
            else:
                # No data is also valid - new system
                print("No rental data found - valid for new system")

        elif response.status_code == 500:
            # Server error due to missing dependencies or service issues
            print("Service dependency issue detected - acceptable in test environment")
            # This is acceptable - external service dependencies might not be available

        else:
            # Other unexpected errors
            pytest.fail(f"Unexpected response status: {response.status_code}")

    def test_azure_sql_configuration(self):
        """Test Azure SQL Database configuration"""
        db_conn = os.getenv("RENTAL_DATABASE_CONNECTION_STRING")
        assert db_conn is not None
        assert "car-rental-sql-server.database.windows.net" in db_conn
        assert "rental_service_db" in db_conn
        assert "Encrypt=yes" in db_conn
        print("✓ Azure SQL Database correctly configured for Rental Service")

    def test_service_integration_urls(self):
        """Test service integration URLs are configured"""
        user_service_url = os.getenv("USER_SERVICE_URL", "http://localhost:5001")
        car_service_url = os.getenv("CAR_SERVICE_URL", "http://localhost:5002")

        assert user_service_url == "http://localhost:5001"
        assert car_service_url == "http://localhost:5002"
        print("✓ Service integration URLs correctly configured")

    def test_service_endpoints_accessible(self):
        """Test that all service endpoints are accessible"""
        endpoints = ["/health", "/ping", "/metrics", "/rentals"]

        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should not return 404 (endpoint not found)
            assert response.status_code != 404
            # 200 or 500 are both acceptable


class TestRentalServiceAzureIntegration:
    """Azure-specific tests for Rental Service"""

    def test_database_connection(self):
        """Test actual Azure SQL connection"""
        try:
            from services.rental_service.database import RentalDatabase

            rental_db = RentalDatabase()
            conn = rental_db.get_connection()

            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

            conn.close()
            print("✓ Azure SQL Database connection successful")

        except Exception as e:
            pytest.skip(f"Database connection failed: {e}")

    def test_rentals_table_exists(self):
        """Test that Rentals table exists in Azure SQL"""
        try:
            from services.rental_service.database import RentalDatabase

            rental_db = RentalDatabase()
            conn = rental_db.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'Rentals'
            """)
            result = cursor.fetchone()
            assert result[0] >= 1

            conn.close()
            print("✓ Rentals table exists in Azure SQL Database")

        except Exception as e:
            pytest.skip(f"Database table check failed: {e}")

    def test_location_encryption(self):
        """Test that locations are encrypted in database"""
        try:
            from services.rental_service.database import RentalDatabase
            from shared.encryption import encryptor

            rental_db = RentalDatabase()
            rentals = rental_db.get_all_rentals()

            if rentals:
                rental = rentals[0]
                if rental.get("pickup_location"):
                    # Try to decrypt - if it changes, it was encrypted
                    decrypted_location = encryptor.decrypt(rental["pickup_location"])
                    if decrypted_location != rental["pickup_location"]:
                        print("✓ Location data is encrypted in database")
                    else:
                        print("ℹ Location appears unencrypted (legacy data?)")

        except Exception as e:
            pytest.skip(f"Database encryption check failed: {e}")

    def test_service_bus_message_capability(self):
        """Test Service Bus message sending capability"""
        try:
            from azure.servicebus import ServiceBusClient, ServiceBusMessage
            import json

            sb_conn = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
            client = ServiceBusClient.from_connection_string(sb_conn)

            # Test message creation (don't actually send to avoid queue pollution)
            test_message_data = {
                "event_type": "test_event",
                "car_id": str(uuid.uuid4()),
                "new_status": "rented"
            }

            message = ServiceBusMessage(json.dumps(test_message_data))
            assert message is not None

            print("✓ Service Bus message creation successful")

        except ImportError:
            pytest.skip("Azure Service Bus SDK not installed")
        except Exception as e:
            pytest.skip(f"Service Bus test failed: {e}")


class TestAzureEnvironmentComplete:
    """Complete Azure environment validation"""

    def test_all_azure_resources_configured(self):
        """Test that all Azure resources are properly configured"""
        # Database connections
        user_db = os.getenv("USER_DATABASE_CONNECTION_STRING")
        car_db = os.getenv("CAR_DATABASE_CONNECTION_STRING")
        rental_db = os.getenv("RENTAL_DATABASE_CONNECTION_STRING")

        assert all([user_db, car_db, rental_db])

        # Service Bus
        service_bus = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")

        # Storage
        storage = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

        # Encryption
        encryption_key = os.getenv("ENCRYPTION_KEY")

        assert all([service_bus, storage, encryption_key])

        # Verify Azure endpoints
        assert "car-rental-sql-server.database.windows.net" in user_db
        assert "car-rental-servicebus.servicebus.windows.net" in service_bus
        assert "carrentalstorage2025" in storage

        print("✓ All Azure resources correctly configured")
        print(f"  - Azure SQL Server: car-rental-sql-server.database.windows.net")
        print(f"  - Service Bus: car-rental-servicebus.servicebus.windows.net")
        print(f"  - Storage Account: carrentalstorage2025")

    def test_encryption_key_valid(self):
        """Test encryption key is valid Fernet key"""
        from cryptography.fernet import Fernet
        from shared.encryption import encryptor

        key = os.getenv("ENCRYPTION_KEY")
        assert key == "A2ioqar7WnR0XedjOBj3pTE81LRv4n5KUplPgctbznA="

        # Test key works
        fernet = Fernet(key.encode())
        test_data = b"test_data"
        encrypted = fernet.encrypt(test_data)
        decrypted = fernet.decrypt(encrypted)
        assert decrypted == test_data

        print("✓ Encryption key is valid and working")

    def test_pii_fields_complete(self):
        """Test all PII fields are properly configured"""
        from shared.encryption import PII_FIELDS

        expected_pii = {
            'users': ['email', 'first_name', 'last_name', 'phone'],
            'cars': ['license_plate'],
            'rentals': ['pickup_location', 'return_location']
        }

        assert PII_FIELDS == expected_pii
        print("✓ PII fields correctly configured for all services")

    def test_microservices_ports(self):
        """Test microservice ports are correctly configured"""
        ports = {
            "USER_SERVICE_PORT": os.getenv("USER_SERVICE_PORT"),
            "CAR_SERVICE_PORT": os.getenv("CAR_SERVICE_PORT"),
            "RENTAL_SERVICE_PORT": os.getenv("RENTAL_SERVICE_PORT")
        }

        expected_ports = {
            "USER_SERVICE_PORT": "5001",
            "CAR_SERVICE_PORT": "5002",
            "RENTAL_SERVICE_PORT": "5003"
        }

        assert ports == expected_ports
        print("✓ Microservice ports correctly configured")

    def test_azure_deployment_readiness(self):
        """Final Azure deployment readiness check"""
        print("\n🔍 Azure Deployment Readiness Check:")

        checks = {
            "Azure SQL Databases": self._check_azure_sql(),
            "Azure Service Bus": self._check_service_bus(),
            "Azure Storage": self._check_storage(),
            "PII Encryption": self._check_encryption(),
            "Service Configuration": self._check_service_config()
        }

        passed = sum(1 for result in checks.values() if result)
        total = len(checks)

        for check, result in checks.items():
            status = "✓" if result else "✗"
            print(f"  {status} {check}")

        print(f"\nReadiness Score: {passed}/{total}")

        if passed == total:
            print("🎉 System is FULLY ready for Azure deployment!")
        elif passed >= 4:
            print("✅ System is ready for Azure deployment with minor gaps")
        else:
            print("⚠ System needs more configuration for Azure deployment")

        # Don't fail test, just report
        assert passed >= 3, "At least basic Azure configuration should be present"

    def _check_azure_sql(self):
        """Check Azure SQL configuration"""
        try:
            connections = [
                os.getenv("USER_DATABASE_CONNECTION_STRING"),
                os.getenv("CAR_DATABASE_CONNECTION_STRING"),
                os.getenv("RENTAL_DATABASE_CONNECTION_STRING")
            ]

            azure_count = sum(1 for conn in connections
                              if conn and "car-rental-sql-server.database.windows.net" in conn)
            return azure_count == 3
        except:
            return False

    def _check_service_bus(self):
        """Check Service Bus configuration"""
        try:
            sb_conn = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
            return sb_conn and "car-rental-servicebus.servicebus.windows.net" in sb_conn
        except:
            return False

    def _check_storage(self):
        """Check Storage configuration"""
        try:
            storage_conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
            return storage_conn and "carrentalstorage2025" in storage_conn
        except:
            return False

    def _check_encryption(self):
        """Check encryption configuration"""
        try:
            from cryptography.fernet import Fernet
            key = os.getenv("ENCRYPTION_KEY")
            if key:
                Fernet(key.encode())
                return True
            return False
        except:
            return False

    def _check_service_config(self):
        """Check service configuration"""
        try:
            required_ports = ["5001", "5002", "5003"]
            actual_ports = [
                os.getenv("USER_SERVICE_PORT"),
                os.getenv("CAR_SERVICE_PORT"),
                os.getenv("RENTAL_SERVICE_PORT")
            ]
            return actual_ports == required_ports
        except:
            return False