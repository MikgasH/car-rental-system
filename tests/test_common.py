import pytest
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from shared.common import DataValidator, ServiceResponse
except ImportError:
    pytest.skip("Shared common module not available", allow_module_level=True)


class TestDataValidator:
    """Test DataValidator utilities"""

    def test_check_duplicate_email(self):
        """Test duplicate email checking"""
        users = [
            {"user_id": "1", "email": "test@example.com"},
            {"user_id": "2", "email": "other@example.com"}
        ]

        assert DataValidator.check_duplicate_email("test@example.com", users) is True

        assert DataValidator.check_duplicate_email("new@example.com", users) is False

        assert DataValidator.check_duplicate_email("test@example.com", users, exclude_user_id="1") is False

    def test_check_duplicate_license_plate(self):
        """Test duplicate license plate checking"""
        cars = [
            {"car_id": "1", "license_plate": "ABC-123"},
            {"car_id": "2", "license_plate": "DEF-456"}
        ]

        assert DataValidator.check_duplicate_license_plate("ABC-123", cars) is True

        assert DataValidator.check_duplicate_license_plate("XYZ-789", cars) is False

        assert DataValidator.check_duplicate_license_plate("ABC-123", cars, exclude_car_id="1") is False

    def test_validate_car_status(self):
        """Test car status validation"""
        # Valid statuses
        assert DataValidator.validate_car_status("available") is True
        assert DataValidator.validate_car_status("rented") is True
        assert DataValidator.validate_car_status("maintenance") is True

        # Invalid status
        assert DataValidator.validate_car_status("invalid") is False
        assert DataValidator.validate_car_status("") is False

    def test_validate_rental_status(self):
        """Test rental status validation"""
        # Valid statuses
        assert DataValidator.validate_rental_status("pending") is True
        assert DataValidator.validate_rental_status("active") is True
        assert DataValidator.validate_rental_status("completed") is True
        assert DataValidator.validate_rental_status("cancelled") is True

        # Invalid status
        assert DataValidator.validate_rental_status("invalid") is False
        assert DataValidator.validate_rental_status("") is False


class TestServiceResponse:
    """Test ServiceResponse model"""

    def test_service_response_creation(self):
        """Test ServiceResponse creation"""
        response = ServiceResponse(success=True, message="Test message", data={"key": "value"})

        assert response.success is True
        assert response.message == "Test message"
        assert response.data == {"key": "value"}
        assert response.timestamp is not None

    def test_service_response_auto_timestamp(self):
        """Test automatic timestamp generation"""
        response = ServiceResponse(success=True, message="Test")

        assert response.timestamp is not None