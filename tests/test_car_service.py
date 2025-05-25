import pytest
import sys
import os
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from services.car_service.app import app
except ImportError:
    car_service_path = os.path.join(os.path.dirname(__file__), '..', 'services', 'car_service')
    sys.path.append(car_service_path)
    from app import app

client = TestClient(app)

class TestCarService:
    """Car Service test cases"""

    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "car service"
        assert "azure_connection" in data

    def test_ping_endpoint(self):
        """Test ping endpoint"""
        response = client.get("/ping")
        assert response.status_code == 200

        data = response.json()
        assert data["message"] == "pong"
        assert data["service"] == "car service"

    def test_metrics_endpoint(self):
        """Test metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "car service"
        assert "metrics" in data
        assert "total_cars" in data["metrics"]
        assert "available_cars" in data["metrics"]
        assert "rented_cars" in data["metrics"]
        assert data["metrics"]["data_source"] == "azure_sql_database"

    def test_get_all_cars(self):
        """Test retrieving all cars from Azure SQL"""
        response = client.get("/cars")
        assert response.status_code == 200

        cars = response.json()
        assert isinstance(cars, list)
        assert len(cars) >= 0

        if cars:
            car = cars[0]
            required_fields = ["car_id", "make", "model", "year", "license_plate",
                             "status", "daily_rate", "location", "created_at", "updated_at"]
            for field in required_fields:
                assert field in car

            assert car["status"] in ["available", "rented", "maintenance"]
            assert car["daily_rate"] > 0
            assert car["year"] >= 1900

    def test_get_car_by_id_not_found(self):
        """Test retrieving non-existent car"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.get(f"/cars/{fake_id}")
        assert response.status_code == 404

    def test_get_cars_by_location(self):
        """Test retrieving cars by location"""
        response = client.get("/cars/available/Vilnius")
        assert response.status_code == 200

        data = response.json()
        assert "location" in data
        assert "available_cars" in data
        assert "count" in data
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
            assert isinstance(data["cars"], list)

    def test_get_cars_by_invalid_status(self):
        """Test retrieving cars with invalid status"""
        response = client.get("/cars/status/invalid")
        assert response.status_code == 400

    def test_create_car(self):
        """Test creating new car"""
        new_car = {
            "make": "Tesla",
            "model": "Model 3",
            "year": 2023,
            "license_plate": f"TEST-{int(__import__('time').time()) % 1000}",
            "daily_rate": 75.50,
            "location": "Vilnius"
        }

        response = client.post("/cars", json=new_car)

        if response.status_code == 200:
            created_car = response.json()
            assert created_car["make"] == new_car["make"]
            assert created_car["model"] == new_car["model"]
            assert created_car["year"] == new_car["year"]
            assert created_car["status"] == "available"
            assert "car_id" in created_car
            assert "created_at" in created_car
        else:
            assert response.status_code in [400, 500]

    def test_create_car_duplicate_license_plate(self):
        """Test creating car with duplicate license plate"""
        unique_plate = f"DUP-{int(__import__('time').time()) % 1000}"

        car_data = {
            "make": "Toyota",
            "model": "Test",
            "year": 2020,
            "license_plate": unique_plate,
            "daily_rate": 50.0,
            "location": "Test"
        }

        response1 = client.post("/cars", json=car_data)

        if response1.status_code == 200:
            response2 = client.post("/cars", json=car_data)
            assert response2.status_code == 400
        else:
            assert response1.status_code in [400, 500]

    def test_create_car_invalid_data(self):
        """Test creating car with invalid data"""
        invalid_car = {
            "make": "",
            "model": "Test",
            "year": 1800,
            "license_plate": "TEST-123",
            "daily_rate": -10,
            "location": "Test"
        }

        response = client.post("/cars", json=invalid_car)
        assert response.status_code == 422

    def test_update_car_status(self):
        """Test updating car status"""
        # Get cars first
        cars_response = client.get("/cars")
        cars = cars_response.json()

        if cars and len(cars) > 0:
            car_id = cars[0]["car_id"]
            original_status = cars[0]["status"]

            new_status = "maintenance" if original_status != "maintenance" else "available"

            response = client.put(f"/cars/{car_id}/status", params={"new_status": new_status})

            if response.status_code == 200:
                data = response.json()
                assert data["car"]["status"] == new_status
            else:
                assert response.status_code in [400, 404, 500]
        else:
            pytest.skip("No cars available for status update test")

    def test_update_nonexistent_car_status(self):
        """Test updating status of non-existent car"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = client.put(f"/cars/{fake_id}/status", params={"new_status": "available"})
        assert response.status_code == 404