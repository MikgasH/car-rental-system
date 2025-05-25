from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from azure_database_client import azure_client
from shared.common import (
    create_service_app,
    run_service,
    ErrorHandler,
    DataValidator,
    ServiceLogger
)

load_dotenv()

service = create_service_app("Car Service", "Car inventory management microservice")
app = service.get_app()


class CarCreate(BaseModel):
    make: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=50)
    year: int = Field(..., ge=1900, le=2030)
    license_plate: str = Field(..., min_length=1, max_length=20)
    daily_rate: float = Field(..., gt=0)
    location: str = Field(..., min_length=1, max_length=100)


class CarResponse(BaseModel):
    car_id: str
    make: str
    model: str
    year: int
    license_plate: str
    status: str
    daily_rate: float
    location: str
    created_at: datetime
    updated_at: datetime


def get_car_metrics():
    """Get car-specific metrics"""
    cars = azure_client.get_cars()
    total_cars = len(cars)
    available_cars = len([car for car in cars if car["status"] == "available"])
    rented_cars = len([car for car in cars if car["status"] == "rented"])
    maintenance_cars = len([car for car in cars if car["status"] == "maintenance"])

    return {
        "total_cars": total_cars,
        "available_cars": available_cars,
        "rented_cars": rented_cars,
        "maintenance_cars": maintenance_cars,
        "average_daily_rate": sum(car["daily_rate"] for car in cars) / total_cars if total_cars > 0 else 0
    }

service.add_metrics_endpoint(get_car_metrics)


@app.get("/cars", response_model=List[CarResponse])
async def get_all_cars():
    """Get all cars"""
    try:
        cars_data = azure_client.get_cars()
        cars = [CarResponse(**car_data) for car_data in cars_data]

        ServiceLogger.log_operation("car-service", "get_all_cars", f"Retrieved {len(cars)} cars")
        return cars

    except Exception as e:
        ErrorHandler.handle_azure_error("car-service", "get_all_cars", e)


@app.get("/cars/{car_id}", response_model=CarResponse)
async def get_car(car_id: str):
    """Get car by ID"""
    try:
        car_data = azure_client.get_car_by_id(car_id)

        if not car_data:
            ErrorHandler.handle_not_found("car-service", "Car", car_id)

        ServiceLogger.log_operation("car-service", "get_car", f"Retrieved car {car_id}")
        return CarResponse(**car_data)

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("car-service", "get_car", e)


@app.get("/cars/available/{location}")
async def get_available_cars_by_location(location: str):
    """Get available cars by location"""
    try:
        all_cars = azure_client.get_cars()
        available_cars = []

        for car_data in all_cars:
            if (car_data["status"] == "available" and
                    location.lower() in car_data["location"].lower()):
                available_cars.append(CarResponse(**car_data))

        ServiceLogger.log_operation("car-service", "search_cars_by_location",
                                    f"Found {len(available_cars)} available cars in {location}")

        return {
            "location": location,
            "available_cars": available_cars,
            "count": len(available_cars)
        }

    except Exception as e:
        ErrorHandler.handle_azure_error("car-service", "search_cars_by_location", e)


@app.get("/cars/status/{status}")
async def get_cars_by_status(status: str):
    """Get cars by status"""
    try:
        if not DataValidator.validate_car_status(status):
            ErrorHandler.handle_validation_error("car-service",
                                                 f"Invalid status. Use: available, rented, maintenance")

        all_cars = azure_client.get_cars()
        filtered_cars = [CarResponse(**car_data) for car_data in all_cars
                         if car_data["status"] == status]

        ServiceLogger.log_operation("car-service", "filter_cars_by_status",
                                    f"Found {len(filtered_cars)} cars with status {status}")

        return {
            "status": status,
            "cars": filtered_cars,
            "count": len(filtered_cars)
        }

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("car-service", "filter_cars_by_status", e)


@app.post("/cars", response_model=CarResponse)
async def create_car(car: CarCreate):
    """Create new car"""
    try:
        existing_cars = azure_client.get_cars()
        if DataValidator.check_duplicate_license_plate(car.license_plate, existing_cars):
            ErrorHandler.handle_validation_error("car-service", "License plate already exists")

        new_car_data = {
            "car_id": f"car-{str(uuid.uuid4())}",
            "make": car.make,
            "model": car.model,
            "year": car.year,
            "license_plate": car.license_plate,
            "daily_rate": car.daily_rate,
            "location": car.location
        }

        created_car_data = azure_client.create_car(new_car_data)

        ServiceLogger.log_operation("car-service", "create_car",
                                    f"Created car {created_car_data['car_id']}")

        return CarResponse(**created_car_data)

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("car-service", "create_car", e)


@app.put("/cars/{car_id}/status")
async def update_car_status(car_id: str, new_status: str):
    """Update car status"""
    try:
        if not DataValidator.validate_car_status(new_status):
            ErrorHandler.handle_validation_error("car-service",
                                                 f"Invalid status. Use: available, rented, maintenance")

        success = azure_client.update_car_status(car_id, new_status)

        if not success:
            ErrorHandler.handle_not_found("car-service", "Car", car_id)

        updated_car_data = azure_client.get_car_by_id(car_id)

        ServiceLogger.log_operation("car-service", "update_car_status",
                                    f"Updated car {car_id} status to {new_status}")

        return {
            "message": f"Car status updated to {new_status}",
            "car": CarResponse(**updated_car_data)
        }

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("car-service", "update_car_status", e)


if __name__ == "__main__":
    run_service(app, "CAR", 5002)