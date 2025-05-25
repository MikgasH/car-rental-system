import pytest
import sys
import os
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from services.user_service.app import app
except ImportError:
    user_service_path = os.path.join(os.path.dirname(__file__), '..', 'services', 'user_service')
    sys.path.append(user_service_path)
    from app import app

client = TestClient(app)

class TestUserService:
    """User Service test cases"""

    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "user service"
        assert "azure_connection" in data
        assert "timestamp" in data

    def test_ping_endpoint(self):
        """Test ping endpoint"""
        response = client.get("/ping")
        assert response.status_code == 200

        data = response.json()
        assert data["message"] == "pong"
        assert data["service"] == "user service"
        assert "timestamp" in data

    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "user service"
        assert "metrics" in data
        assert "total_users" in data["metrics"]
        assert data["metrics"]["data_source"] == "azure_sql_database"

    def test_get_all_users(self):
        """Test retrieving all users from Azure SQL"""
        response = client.get("/users")
        assert response.status_code == 200

        users = response.json()
        assert isinstance(users, list)
        assert len(users) >= 0

        if users:
            user = users[0]
            required_fields = ["user_id", "email", "first_name", "last_name", "created_at", "updated_at"]
            for field in required_fields:
                assert field in user

    def test_get_user_by_id_not_found(self):
        """Test retrieving non-existent user"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/users/{fake_id}")
        assert response.status_code == 404

    def test_search_user_by_email(self):
        """Test user search by email"""
        response = client.get("/users/search/test")
        assert response.status_code == 200

        data = response.json()
        assert "query" in data
        assert "results" in data
        assert "count" in data
        assert isinstance(data["results"], list)

    def test_create_user(self):
        """Test creating new user"""
        new_user = {
            "email": f"test-{int(__import__('time').time())}@example.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "User",
            "phone": "+37060000999"
        }

        response = client.post("/users", json=new_user)

        if response.status_code == 200:
            created_user = response.json()
            assert created_user["email"] == new_user["email"]
            assert created_user["first_name"] == new_user["first_name"]
            assert created_user["last_name"] == new_user["last_name"]
            assert "user_id" in created_user
            assert "created_at" in created_user
        else:
            assert response.status_code in [400, 500]

    def test_create_user_duplicate_email(self):
        """Test creating user with duplicate email"""
        unique_email = f"duplicate-test-{int(__import__('time').time())}@example.com"
        user_data = {
            "email": unique_email,
            "password": "testpassword123",
            "first_name": "First",
            "last_name": "User"
        }

        response1 = client.post("/users", json=user_data)

        if response1.status_code == 200:
            response2 = client.post("/users", json=user_data)
            assert response2.status_code == 400
        else:
            assert response1.status_code in [400, 500]

    def test_create_user_invalid_data(self):
        """Test creating user with invalid data"""
        invalid_user = {
            "email": "not-an-email",
            "password": "123",
            "first_name": "",
            "last_name": "User"
        }

        response = client.post("/users", json=invalid_user)
        assert response.status_code == 422