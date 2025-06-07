import pytest
import sys
import os
from fastapi.testclient import TestClient
import uuid
import time

# --- КОРРЕКТНЫЙ БЛОК ДЛЯ ИМПОРТА ---
# Добавляем корневую директорию проекта в sys.path
# Если этот файл находится в `your_project_root/tests/`,
# то '..' поднимет нас в `your_project_root/`
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, project_root)
# --- КОНЕЦ КОРРЕКТНОГО БЛОКА ---

# Теперь импорты должны работать корректно
from services.user_service.app import app
from shared.encryption import encryptor, PII_FIELDS # Если используются в тестах

client = TestClient(app)

class TestUserService:
    """User Service test cases"""

    # --- Общие эндпоинты (Health, Metrics) ---
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "User Service" # Проверьте точное название сервиса
        assert "azure_connection" in data
        assert "timestamp" in data

    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "User Service" # Проверьте точное название сервиса
        assert "metrics" in data
        assert "total_users" in data["metrics"]
        assert "active_users" in data["metrics"]


    # --- Тестирование CRUD операций с User ---

    def test_create_and_get_user(self):
        """Test creating new user and then retrieving it"""
        unique_email = f"test.user.{int(time.time())}.{uuid.uuid4().hex[:8]}@example.com"
        new_user_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": unique_email,
            "phone": "+37060000003"
            # "address" - удалено
        }

        # Create user
        response_create = client.post("/users", json=new_user_data)
        assert response_create.status_code == 200, f"Expected 200, got {response_create.status_code}: {response_create.json()}"
        created_user = response_create.json()

        assert "user_id" in created_user
        assert created_user["email"] == new_user_data["email"] # В ответе API должно быть расшифровано
        assert created_user["first_name"] == new_user_data["first_name"]
        assert created_user["last_name"] == new_user_data["last_name"]
        assert created_user["phone"] == new_user_data["phone"] # В ответе API должно быть расшифровано
        # assert "password" not in created_user # Пароль не должен возвращаться в ответе

        # Get user by ID
        user_id = created_user["user_id"]
        response_get = client.get(f"/users/{user_id}")
        assert response_get.status_code == 200
        retrieved_user = response_get.json()

        assert retrieved_user["user_id"] == user_id
        assert retrieved_user["email"] == unique_email # Должно быть расшифровано
        assert retrieved_user["phone"] == new_user_data["phone"] # Должно быть расшифровано


    def test_get_all_users(self):
        """Test retrieving all users"""
        response = client.get("/users")
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)

        if users:
            user = users[0]
            required_fields = ["user_id", "email", "first_name", "last_name", "phone", "created_at", "updated_at"]
            for field in required_fields:
                assert field in user
            assert len(user["email"]) > 0 # Проверяем, что PII расшифрованы и не пусты
            assert len(user["first_name"]) > 0
            assert len(user["last_name"]) > 0
            assert len(user["phone"]) > 0


    def test_get_user_by_id_not_found(self):
        """Test retrieving non-existent user"""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/users/{fake_id}")
        assert response.status_code == 404

    # Этот тест был для эндпоинта /users/search/{email_query},
    # которого в текущем app.py нет. Если он нужен, добавьте его.
    # def test_search_user_by_email(self):
    #     """Test user search by email"""
    #     # Вам нужно сначала создать пользователя с известным email
    #     response = client.get("/users/search/test")
    #     assert response.status_code == 200
    #     data = response.json()
    #     assert "query" in data
    #     assert "results" in data
    #     assert "count" in data
    #     assert isinstance(data["results"], list)

    def test_create_user_duplicate_email(self):
        """Test creating user with duplicate email"""
        unique_email = f"duplicate-{int(time.time())}.{uuid.uuid4().hex[:8]}@example.com"
        user_data = {
            "email": unique_email,
            "first_name": "First",
            "last_name": "User",
            "phone": "+37060000004"
            # "address" - удалено
        }

        response1 = client.post("/users", json=user_data)
        assert response1.status_code == 200 # First creation should be successful

        response2 = client.post("/users", json=user_data)
        assert response2.status_code == 400 # Duplicate should fail
        assert "Email already exists" in response2.json()["detail"]


    def test_create_user_invalid_data(self):
        """Test creating user with invalid data"""
        invalid_user = {
            "email": "not-an-email",  # Invalid email format
            "first_name": "",         # Too short
            "last_name": "User",
            "phone": "short"          # Too short
            # "address" - удалено
        }
        response = client.post("/users", json=invalid_user)
        assert response.status_code == 422 # Pydantic validation error


    def test_update_user(self):
        """Test updating an existing user"""
        # 1. Create a user to update
        initial_email = f"update.{int(time.time())}.{uuid.uuid4().hex[:8]}@example.com"
        create_data = {
            "first_name": "Initial", "last_name": "User", "email": initial_email, "phone": "+37060000005"
        }
        create_resp = client.post("/users", json=create_data)
        assert create_resp.status_code == 200
        user_id = create_resp.json()["user_id"]

        # 2. Prepare update data
        updated_first_name = "Updated"
        updated_email = f"new.update.{int(time.time())}.{uuid.uuid4().hex[:8]}@example.com"
        updated_phone = "+37060000006"

        update_data = {
            "first_name": updated_first_name,
            "last_name": "User", # Keep same or change
            "email": updated_email,
            "phone": updated_phone
        }
        response = client.put(f"/users/{user_id}", json=update_data)
        assert response.status_code == 200

        updated_user = response.json()
        assert updated_user["user_id"] == user_id
        assert updated_user["first_name"] == updated_first_name
        assert updated_user["email"] == updated_email
        assert updated_user["phone"] == updated_phone
        assert updated_user["updated_at"] > updated_user["created_at"]


    def test_update_nonexistent_user(self):
        """Test updating a non-existent user"""
        fake_id = str(uuid.uuid4())
        update_data = {
            "first_name": "NonExistent", "last_name": "Test", "email": "nonexistent@example.com", "phone": "+37060000007"
        }
        response = client.put(f"/users/{fake_id}", json=update_data)
        assert response.status_code == 404


    def test_delete_user(self):
        """Test deleting a user"""
        # 1. Create a user to delete
        create_data = {
            "first_name": "Delete", "last_name": "Me", "email": f"delete.{int(time.time())}.{uuid.uuid4().hex[:8]}@example.com", "phone": "+37060000008"
        }
        create_resp = client.post("/users", json=create_data)
        assert create_resp.status_code == 200
        user_id = create_resp.json()["user_id"]

        # 2. Delete the user
        response_delete = client.delete(f"/users/{user_id}")
        assert response_delete.status_code == 200
        assert response_delete.json()["message"] == "User deleted successfully"

        # 3. Try to retrieve the deleted user
        response_get = client.get(f"/users/{user_id}")
        assert response_get.status_code == 404

    def test_delete_nonexistent_user(self):
        """Test deleting a non-existent user"""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/users/{fake_id}")
        assert response.status_code == 404