import pytest
import sys
import os
from fastapi.testclient import TestClient

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import the app
try:
    from services.rental_service.app import app
except ImportError:
    rental_service_path = os.path.join(os.path.dirname(__file__), '..', 'services', 'rental_service')
    sys.path.append(rental_service_path)
    from app import app

client = TestClient(app)

class TestRentalService:
    """Rental Service test cases"""

    def test_health_endpoint(self):
        """Test health check endpoint - EXACT match to old code expectations"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "rental-service"
        assert "azure_connection" in data
        assert "dependencies" in data
        assert "timestamp" in data

    def test_ping_endpoint(self):
        """Test ping endpoint"""
        response = client.get("/ping")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "pong"
        assert data["service"] == "rental-service"

    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "rental-service"
        assert "metrics" in data

    def test_get_all_rentals(self):
        """Test retrieving all rentals"""
        response = client.get("/rentals")
        assert response.status_code == 200
        rentals = response.json()
        assert isinstance(rentals, list)

    def test_get_rental_by_id_not_found(self):
        """Test retrieving non-existent rental"""
        fake_id = "rental-00000000-0000-0000-0000-000000000000"
        response = client.get(f"/rentals/{fake_id}")
        assert response.status_code == 404

    def test_create_rental_invalid_dates(self):
        """Test creating rental with invalid dates"""
        invalid_rental = {
            "user_id": "550e8400-e29b-41d4-a716-446655440001",
            "car_id": "car-550e8400-e29b-41d4-a716-446655440001",
            "start_date": "2025-05-30T10:00:00Z",
            "end_date": "2025-05-29T10:00:00Z",
            "pickup_location": "Vilnius Airport",
            "return_location": "Vilnius Airport"
        }
        response = client.post("/rentals", json=invalid_rental)
        assert response.status_code == 400

    def test_create_rental_past_date(self):
        """Test creating rental with past date"""
        past_rental = {
            "user_id": "550e8400-e29b-41d4-a716-446655440001",
            "car_id": "car-550e8400-e29b-41d4-a716-446655440001",
            "start_date": "2020-01-01T10:00:00Z",
            "end_date": "2020-01-05T10:00:00Z",
            "pickup_location": "Vilnius Airport",
            "return_location": "Vilnius Airport"
        }
        response = client.post("/rentals", json=past_rental)
        assert response.status_code == 400

    def test_create_rental_nonexistent_user(self):
        """Test creating rental with non-existent user"""
        rental_data = {
            "user_id": "00000000-0000-0000-0000-000000000000",
            "car_id": "car-550e8400-e29b-41d4-a716-446655440001",
            "start_date": "2025-06-01T10:00:00Z",
            "end_date": "2025-06-05T10:00:00Z",
            "pickup_location": "Vilnius Airport",
            "return_location": "Vilnius Airport"
        }
        response = client.post("/rentals", json=rental_data)
        assert response.status_code == 404

    def test_create_rental_nonexistent_car(self):
        """Test creating rental with non-existent car"""
        rental_data = {
            "user_id": "550e8400-e29b-41d4-a716-446655440001",
            "car_id": "00000000-0000-0000-0000-000000000000",
            "start_date": "2025-06-01T10:00:00Z",
            "end_date": "2025-06-05T10:00:00Z",
            "pickup_location": "Vilnius Airport",
            "return_location": "Vilnius Airport"
        }
        response = client.post("/rentals", json=rental_data)
        assert response.status_code == 404

    def test_create_rental_invalid_data(self):
        """Test creating rental with invalid data format"""
        invalid_rental = {
            "user_id": "not-a-uuid",
            "car_id": "also-not-a-uuid",
            "start_date": "not-a-date",
            "end_date": "2025-05-30T10:00:00Z",
            "pickup_location": "",
            "return_location": "Vilnius Airport"
        }
        response = client.post("/rentals", json=invalid_rental)
        assert response.status_code == 422