from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from azure_database_client import azure_client

load_dotenv()

app = FastAPI(title="Car Service", version="1.0.0")


class Car(BaseModel):
    car_id: Optional[str] = None
    make: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=50)
    year: int = Field(..., ge=1900, le=2030)
    license_plate: str = Field(..., min_length=1, max_length=20)
    status: str = Field(..., pattern="^(available|rented|maintenance)$")
    daily_rate: float = Field(..., gt=0)
    location: str = Field(..., min_length=1, max_length=100)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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


@app.get("/health")
async def health_check():
    """Health check endpoint with Azure connection info"""
    try:
        azure_client.log_to_azure("car-service", "INFO", "Health check passed")

        azure_info = azure_client.get_connection_info()

        return {
            "status": "healthy",
            "service": "car-service",
            "azure_connection": azure_info,
            "timestamp": datetime.now(timezone.utc)
        }
    except Exception as e:
        azure_client.log_to_azure("car-service", "ERROR", f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "car-service",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc)
        }


@app.get("/ping")
async def ping():
    """Ping endpoint"""
    return {
        "message": "pong",
        "service": "car-service",
        "timestamp": datetime.now(timezone.utc)
    }


@app.get("/metrics")
async def metrics():
    """Metrics endpoint with Azure data"""
    try:
        cars = azure_client.get_cars()
        total_cars = len(cars)
        available_cars = len([car for car in cars if car["status"] == "available"])
        rented_cars = len([car for car in cars if car["status"] == "rented"])
        maintenance_cars = len([car for car in cars if car["status"] == "maintenance"])

        metrics_data = {
            "service": "car-service",
            "timestamp": datetime.now(timezone.utc),
            "metrics": {
                "total_cars": total_cars,
                "available_cars": available_cars,
                "rented_cars": rented_cars,
                "maintenance_cars": maintenance_cars,
                "average_daily_rate": sum(car["daily_rate"] for car in cars) / total_cars if total_cars > 0 else 0,
                "status": "operational",
                "data_source": "azure_sql_database"
            }
        }

        azure_client.log_to_azure("car-service", "INFO", "Metrics requested")
        return metrics_data

    except Exception as e:
        azure_client.log_to_azure("car-service", "ERROR", f"Metrics endpoint failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")


@app.get("/cars", response_model=List[CarResponse])
async def get_all_cars():
    """Get all cars from Azure SQL Database"""
    try:
        cars_data = azure_client.get_cars()
        cars = [CarResponse(**car_data) for car_data in cars_data]

        azure_client.log_to_azure("car-service", "INFO", f"Retrieved {len(cars)} cars from Azure SQL")
        return cars
    except Exception as e:
        azure_client.log_to_azure("car-service", "ERROR", f"Failed to get cars: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve cars: {str(e)}")


@app.get("/cars/{car_id}", response_model=CarResponse)
async def get_car(car_id: str):
    """Get car by ID from Azure SQL Database"""
    try:
        car_data = azure_client.get_car_by_id(car_id)

        if not car_data:
            raise HTTPException(status_code=404, detail="Car not found")

        car = CarResponse(**car_data)
        azure_client.log_to_azure("car-service", "INFO", f"Retrieved car {car_id} from Azure SQL", car_id)
        return car

    except HTTPException:
        raise
    except Exception as e:
        azure_client.log_to_azure("car-service", "ERROR", f"Failed to get car {car_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve car: {str(e)}")


@app.get("/cars/available/{location}")
async def get_available_cars_by_location(location: str):
    """Get available cars by location from Azure SQL Database"""
    try:
        all_cars = azure_client.get_cars()
        available_cars = []

        for car_data in all_cars:
            if (car_data["status"] == "available" and location.lower() in car_data["location"].lower()):
                car = CarResponse(**car_data)
                available_cars.append(car)

        azure_client.log_to_azure("car-service", "INFO",
                                  f"Found {len(available_cars)} available cars in {location} from Azure SQL")
        return {"location": location, "available_cars": available_cars, "count": len(available_cars)}

    except Exception as e:
        azure_client.log_to_azure("car-service", "ERROR", f"Failed to search cars by location: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/cars/status/{status}")
async def get_cars_by_status(status: str):
    """Get cars by status from Azure SQL Database"""
    try:
        valid_statuses = ["available", "rented", "maintenance"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Use: {', '.join(valid_statuses)}")

        all_cars = azure_client.get_cars()
        filtered_cars = []

        for car_data in all_cars:
            if car_data["status"] == status:
                car = CarResponse(**car_data)
                filtered_cars.append(car)

        azure_client.log_to_azure("car-service", "INFO",
                                  f"Found {len(filtered_cars)} cars with status {status} from Azure SQL")
        return {"status": status, "cars": filtered_cars, "count": len(filtered_cars)}

    except HTTPException:
        raise
    except Exception as e:
        azure_client.log_to_azure("car-service", "ERROR", f"Failed to filter cars by status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Filter failed: {str(e)}")


@app.post("/cars", response_model=CarResponse)
async def create_car(car: CarCreate):
    """Create new car in Azure SQL Database"""
    try:
        existing_cars = azure_client.get_cars()
        for existing_car in existing_cars:
            if existing_car["license_plate"] == car.license_plate:
                raise HTTPException(status_code=400, detail="License plate already exists")

        car_id = f"car-{str(uuid.uuid4())}"
        new_car_data = {
            "car_id": car_id,
            "make": car.make,
            "model": car.model,
            "year": car.year,
            "license_plate": car.license_plate,
            "status": "available",
            "daily_rate": car.daily_rate,
            "location": car.location
        }

        created_car_data = azure_client.create_car(new_car_data)
        created_car = CarResponse(**created_car_data)

        azure_client.log_to_azure("car-service", "INFO", f"Created new car {car_id} in Azure SQL", car_id)
        return created_car

    except HTTPException:
        raise
    except Exception as e:
        azure_client.log_to_azure("car-service", "ERROR", f"Failed to create car: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create car: {str(e)}")


@app.put("/cars/{car_id}/status")
async def update_car_status(car_id: str, new_status: str):
    """Update car status in Azure SQL Database"""
    try:
        valid_statuses = ["available", "rented", "maintenance"]
        if new_status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Use: {', '.join(valid_statuses)}")

        success = azure_client.update_car_status(car_id, new_status)

        if not success:
            raise HTTPException(status_code=404, detail="Car not found")

        updated_car_data = azure_client.get_car_by_id(car_id)
        updated_car = CarResponse(**updated_car_data)

        azure_client.log_to_azure("car-service", "INFO",
                                  f"Updated car {car_id} status to {new_status} in Azure SQL", car_id)
        return {
            "message": f"Car status updated to {new_status}",
            "car": updated_car
        }

    except HTTPException:
        raise
    except Exception as e:
        azure_client.log_to_azure("car-service", "ERROR", f"Failed to update car status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update car status: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("CAR_SERVICE_PORT", 5002))
    azure_client.log_to_azure("car-service", "INFO", f"Starting Car Service on port {port}")
    print(f"🚗 Starting Car Service with Azure SQL on http://localhost:{port}")
    print(f"📚 API Documentation: http://localhost:{port}/docs")
    print(f"❤️  Health Check: http://localhost:{port}/health")
    uvicorn.run(app, host="0.0.0.0", port=port)