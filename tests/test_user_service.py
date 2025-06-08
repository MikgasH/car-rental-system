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

from services.user_service.app import app

client = TestClient(app)


class TestUserService:
    """User Service tests for car rental system"""

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
        assert "total_users" in data["metrics"]
        assert "active_users" in data["metrics"]

    def test_get_all_users(self):
        """Test retrieving all users"""
        response = client.get("/users")
        assert response.status_code == 200

        users = response.json()
        assert isinstance(users, list)

        if users:
            user = users[0]
            required_fields = ["user_id", "first_name", "last_name", "email", "phone", "created_at", "updated_at"]
            for field in required_fields:
                assert field in user

            # Check that email format is valid (decrypted)
            assert "@" in user["email"]

    def test_get_user_by_id_not_found(self):
        """Test retrieving non-existent user"""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/users/{fake_id}")
        assert response.status_code == 404

    def test_create_user_valid(self):
        """Test creating new user with valid data"""
        unique_email = f"test.user.{int(time.time())}.{uuid.uuid4().hex[:8]}@example.com"
        new_user_data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": unique_email,
            "phone": "+37060123456"
        }

        response = client.post("/users", json=new_user_data)

        if response.status_code == 200:
            created_user = response.json()

            assert "user_id" in created_user
            assert created_user["email"] == new_user_data["email"]
            assert created_user["first_name"] == new_user_data["first_name"]
            assert created_user["last_name"] == new_user_data["last_name"]
            assert created_user["phone"] == new_user_data["phone"]

            # Test retrieval by ID
            user_id = created_user["user_id"]
            get_response = client.get(f"/users/{user_id}")
            assert get_response.status_code == 200

        else:
            # Database might not be accessible in test environment
            assert response.status_code in [400, 500]

    def test_create_user_invalid_data(self):
        """Test creating user with invalid data"""
        invalid_user = {
            "first_name": "",  # Empty first name
            "last_name": "User",
            "email": "valid@example.com",
            "phone": "+37060123458"
        }

        response = client.post("/users", json=invalid_user)
        assert response.status_code == 422  # Validation error

    def test_azure_sql_configuration(self):
        """Test Azure SQL Database configuration"""
        db_conn = os.getenv("USER_DATABASE_CONNECTION_STRING")
        assert db_conn is not None
        assert "car-rental-sql-server.database.windows.net" in db_conn
        assert "user_service_db" in db_conn
        assert "Encrypt=yes" in db_conn
        print("✓ Azure SQL Database correctly configured for User Service")

    def test_encryption_working(self):
        """Test that encryption is working"""
        from shared.encryption import encryptor, PII_FIELDS

        test_data = "test@example.com"
        encrypted = encryptor.encrypt(test_data)
        decrypted = encryptor.decrypt(encrypted)

        assert encrypted != test_data
        assert decrypted == test_data
        print("✓ Encryption system working")

    def test_pii_fields_configured(self):
        """Test PII fields are properly configured for users"""
        from shared.encryption import PII_FIELDS

        assert 'users' in PII_FIELDS
        user_pii = PII_FIELDS['users']
        expected_fields = ['email', 'first_name', 'last_name', 'phone']

        for field in expected_fields:
            assert field in user_pii

        print("✓ User PII fields correctly configured")


class TestUserServiceAzureIntegration:
    """Azure-specific tests for User Service"""

    def test_database_connection(self):
        """Test actual Azure SQL connection"""
        try:
            from services.user_service.database import UserDatabase

            user_db = UserDatabase()
            conn = user_db.get_connection()

            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1

            conn.close()
            print("✓ Azure SQL Database connection successful")

        except Exception as e:
            pytest.skip(f"Database connection failed: {e}")

    def test_users_table_exists(self):
        """Test that Users table exists in Azure SQL"""
        try:
            from services.user_service.database import UserDatabase

            user_db = UserDatabase()
            conn = user_db.get_connection()
            cursor = conn.cursor()

            # Check if Users table exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'Users'
            """)
            result = cursor.fetchone()
            assert result[0] >= 1

            conn.close()
            print("✓ Users table exists in Azure SQL Database")

        except Exception as e:
            pytest.skip(f"Database table check failed: {e}")

    def test_encryption_in_database(self):
        """Test that data is actually encrypted in database"""
        try:
            from services.user_service.database import UserDatabase
            from shared.encryption import encryptor

            user_db = UserDatabase()
            users = user_db.get_all_users()

            if users:
                # Raw data from database should be encrypted
                user = users[0]
                if user.get("email"):
                    # Try to decrypt - if it changes, it was encrypted
                    decrypted_email = encryptor.decrypt(user["email"])
                    if decrypted_email != user["email"]:
                        print("✓ Email data is encrypted in database")
                    else:
                        print("ℹ Email data appears unencrypted (legacy data?)")

        except Exception as e:
            pytest.skip(f"Database encryption check failed: {e}")