import pytest
import sys
import os
from datetime import datetime, timezone

# Add project root to path
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, project_root)

try:
    from shared.common import (
        DataValidator,
        ServiceResponse,
        ErrorHandler,
        ServiceLogger,
        BaseService,
        create_service_app
    )
    from shared.encryption import encryptor, PII_FIELDS
except ImportError as e:
    pytest.skip(f"Shared modules not available: {e}", allow_module_level=True)


class TestDataValidator:
    """Test DataValidator utilities"""

    def test_check_duplicate_email(self):
        """Test duplicate email checking"""
        users = [
            {"user_id": "user-1", "email": "test@example.com"},
            {"user_id": "user-2", "email": "other@example.com"},
            {"user_id": "user-3", "email": "admin@example.com"}
        ]

        # Test duplicate detection
        assert DataValidator.check_duplicate_email("test@example.com", users) is True
        assert DataValidator.check_duplicate_email("other@example.com", users) is True

        # Test non-duplicate
        assert DataValidator.check_duplicate_email("new@example.com", users) is False
        assert DataValidator.check_duplicate_email("unique@example.com", users) is False

        # Test with exclude_user_id
        assert DataValidator.check_duplicate_email("test@example.com", users, exclude_user_id="user-1") is False
        assert DataValidator.check_duplicate_email("test@example.com", users, exclude_user_id="user-2") is True

    def test_check_duplicate_license_plate(self):
        """Test duplicate license plate checking"""
        cars = [
            {"car_id": "car-1", "license_plate": "ABC-123"},
            {"car_id": "car-2", "license_plate": "DEF-456"},
            {"car_id": "car-3", "license_plate": "GHI-789"}
        ]

        # Test duplicate detection
        assert DataValidator.check_duplicate_license_plate("ABC-123", cars) is True
        assert DataValidator.check_duplicate_license_plate("DEF-456", cars) is True

        # Test non-duplicate
        assert DataValidator.check_duplicate_license_plate("XYZ-999", cars) is False
        assert DataValidator.check_duplicate_license_plate("NEW-001", cars) is False

        # Test with exclude_car_id
        assert DataValidator.check_duplicate_license_plate("ABC-123", cars, exclude_car_id="car-1") is False
        assert DataValidator.check_duplicate_license_plate("ABC-123", cars, exclude_car_id="car-2") is True

    def test_validate_car_status(self):
        """Test car status validation"""
        # Valid statuses
        valid_statuses = ["available", "rented", "maintenance"]
        for status in valid_statuses:
            assert DataValidator.validate_car_status(status) is True

        # Invalid statuses
        invalid_statuses = ["invalid", "unknown", "broken", "sold", "", None]
        for status in invalid_statuses:
            assert DataValidator.validate_car_status(status) is False

    def test_validate_rental_status(self):
        """Test rental status validation"""
        # Valid statuses
        valid_statuses = ["pending", "active", "completed", "cancelled"]
        for status in valid_statuses:
            assert DataValidator.validate_rental_status(status) is True

        # Invalid statuses
        invalid_statuses = ["invalid", "processing", "unknown", "", None]
        for status in invalid_statuses:
            assert DataValidator.validate_rental_status(status) is False


class TestServiceResponse:
    """Test ServiceResponse model"""

    def test_service_response_creation(self):
        """Test ServiceResponse creation with all fields"""
        response = ServiceResponse(
            success=True,
            message="Operation completed",
            data={"key": "value", "count": 42}
        )

        assert response.success is True
        assert response.message == "Operation completed"
        assert response.data == {"key": "value", "count": 42}
        assert response.timestamp is not None
        assert isinstance(response.timestamp, datetime)

    def test_service_response_auto_timestamp(self):
        """Test automatic timestamp generation"""
        response1 = ServiceResponse(success=True, message="Test 1")
        response2 = ServiceResponse(success=True, message="Test 2")

        assert response1.timestamp is not None
        assert response2.timestamp is not None
        assert response2.timestamp >= response1.timestamp

    def test_service_response_with_custom_timestamp(self):
        """Test ServiceResponse with custom timestamp"""
        custom_time = datetime.now(timezone.utc)
        response = ServiceResponse(
            success=False,
            message="Custom time",
            timestamp=custom_time
        )

        assert response.timestamp == custom_time
        assert response.success is False

    def test_service_response_minimal(self):
        """Test ServiceResponse with minimal data"""
        response = ServiceResponse(success=True, message="Minimal")

        assert response.success is True
        assert response.message == "Minimal"
        assert response.data is None
        assert response.timestamp is not None


class TestEncryption:
    """Test encryption utilities"""

    def test_encrypt_decrypt_string(self):
        """Test string encryption and decryption"""
        original_text = "sensitive_data_123"

        # Encrypt
        encrypted = encryptor.encrypt(original_text)
        assert encrypted != original_text
        assert len(encrypted) > len(original_text)

        # Decrypt
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == original_text

    def test_encrypt_decrypt_empty_string(self):
        """Test encryption of empty strings"""
        empty_string = ""
        encrypted = encryptor.encrypt(empty_string)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == empty_string

    def test_encrypt_decrypt_none(self):
        """Test encryption of None values"""
        none_value = None
        encrypted = encryptor.encrypt(none_value)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == none_value

    def test_encrypt_decrypt_dict_user_data(self):
        """Test dictionary encryption for user data"""
        user_data = {
            "user_id": "user-123",
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "phone": "+37060123456",
            "created_at": "2025-06-08T10:00:00Z"
        }

        # Encrypt PII fields
        encrypted_data = encryptor.encrypt_dict(user_data, PII_FIELDS['users'])

        # Check that PII fields are encrypted
        for field in PII_FIELDS['users']:
            if field in user_data and user_data[field]:
                assert encrypted_data[field] != user_data[field]

        # Check that non-PII fields remain unchanged
        assert encrypted_data["user_id"] == user_data["user_id"]
        assert encrypted_data["created_at"] == user_data["created_at"]

        # Decrypt and verify
        decrypted_data = encryptor.decrypt_dict(encrypted_data, PII_FIELDS['users'])
        assert decrypted_data == user_data

    def test_encrypt_decrypt_dict_car_data(self):
        """Test dictionary encryption for car data"""
        car_data = {
            "car_id": "car-123",
            "make": "Toyota",
            "model": "Camry",
            "license_plate": "ABC-123",
            "year": 2023,
            "daily_rate": 50.0,
            "status": "available"
        }

        # Encrypt PII fields
        encrypted_data = encryptor.encrypt_dict(car_data, PII_FIELDS['cars'])

        # Check that license_plate is encrypted
        assert encrypted_data["license_plate"] != car_data["license_plate"]

        # Check that other fields remain unchanged
        assert encrypted_data["make"] == car_data["make"]
        assert encrypted_data["model"] == car_data["model"]
        assert encrypted_data["year"] == car_data["year"]

        # Decrypt and verify
        decrypted_data = encryptor.decrypt_dict(encrypted_data, PII_FIELDS['cars'])
        assert decrypted_data == car_data

    def test_encrypt_decrypt_dict_rental_data(self):
        """Test dictionary encryption for rental data"""
        rental_data = {
            "rental_id": "rental-123",
            "user_id": "user-123",
            "car_id": "car-123",
            "pickup_location": "Vilnius Airport",
            "return_location": "Kaunas Center",
            "start_date": "2025-06-15T10:00:00Z",
            "total_amount": 150.0
        }

        # Encrypt PII fields
        encrypted_data = encryptor.encrypt_dict(rental_data, PII_FIELDS['rentals'])

        # Check that location fields are encrypted
        assert encrypted_data["pickup_location"] != rental_data["pickup_location"]
        assert encrypted_data["return_location"] != rental_data["return_location"]

        # Check that other fields remain unchanged
        assert encrypted_data["rental_id"] == rental_data["rental_id"]
        assert encrypted_data["total_amount"] == rental_data["total_amount"]

        # Decrypt and verify
        decrypted_data = encryptor.decrypt_dict(encrypted_data, PII_FIELDS['rentals'])
        assert decrypted_data == rental_data

    def test_pii_fields_configuration(self):
        """Test PII fields configuration"""
        assert 'users' in PII_FIELDS
        assert 'cars' in PII_FIELDS
        assert 'rentals' in PII_FIELDS

        # Check user PII fields
        user_pii = PII_FIELDS['users']
        expected_user_fields = ['email', 'first_name', 'last_name', 'phone']
        for field in expected_user_fields:
            assert field in user_pii

        # Check car PII fields
        car_pii = PII_FIELDS['cars']
        assert 'license_plate' in car_pii

        # Check rental PII fields
        rental_pii = PII_FIELDS['rentals']
        expected_rental_fields = ['pickup_location', 'return_location']
        for field in expected_rental_fields:
            assert field in rental_pii


class TestBaseService:
    """Test BaseService functionality"""

    def test_create_service_app(self):
        """Test service app creation"""
        service = create_service_app("Test Service", "Test description")

        assert service.service_name == "Test Service"
        app = service.get_app()

        # Check that app is FastAPI instance
        assert hasattr(app, 'routes')
        assert hasattr(app, 'title')
        assert app.title == "Test Service"

    def test_base_service_endpoints(self):
        """Test that base service has required endpoints"""
        from fastapi.testclient import TestClient

        service = create_service_app("Test Service")
        app = service.get_app()
        client = TestClient(app)

        # Test health endpoint
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "test service"

        # Test ping endpoint
        response = client.get("/ping")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "pong"
        assert data["service"] == "test service"


class TestServiceLogger:
    """Test ServiceLogger functionality"""

    def test_service_logger_operations(self):
        """Test service logging operations"""
        # These tests mainly ensure the logger doesn't crash
        # In a real environment, you'd check actual log outputs

        try:
            ServiceLogger.log_operation("test-service", "test_operation", "Test details")
            ServiceLogger.log_error("test-service", "test_operation", "Test error")
            ServiceLogger.log_warning("test-service", "test_operation", "Test warning")

            # With user_id
            ServiceLogger.log_operation("test-service", "test_operation", "Test details", "user-123")
            ServiceLogger.log_error("test-service", "test_operation", "Test error", "user-123")
            ServiceLogger.log_warning("test-service", "test_operation", "Test warning", "user-123")

            # Test passes if no exceptions are raised
            assert True
        except Exception as e:
            pytest.fail(f"ServiceLogger operations should not raise exceptions: {e}")


class TestIntegration:
    """Integration tests for shared components"""

    def test_full_data_flow(self):
        """Test complete data flow with encryption and validation"""
        # Create user data
        user_data = {
            "user_id": "user-123",
            "email": "integration@test.com",
            "first_name": "Integration",
            "last_name": "Test",
            "phone": "+37060999999"
        }

        # Validate duplicate check works
        existing_users = [user_data]
        assert DataValidator.check_duplicate_email("integration@test.com", existing_users) is True
        assert DataValidator.check_duplicate_email("different@test.com", existing_users) is False

        # Test encryption workflow
        encrypted_user = encryptor.encrypt_dict(user_data, PII_FIELDS['users'])
        decrypted_user = encryptor.decrypt_dict(encrypted_user, PII_FIELDS['users'])

        assert decrypted_user == user_data

        # Test service response
        response = ServiceResponse(
            success=True,
            message="Integration test completed",
            data=decrypted_user
        )

        assert response.success is True
        assert response.data == user_data