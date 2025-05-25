from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import uuid
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import requests

import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from azure_database_client import azure_client

load_dotenv()

app = FastAPI(title="Rental Service", version="1.0.0")

USER_SERVICE_URL = f"http://localhost:{os.getenv('USER_SERVICE_PORT', 5001)}"
CAR_SERVICE_URL = f"http://localhost:{os.getenv('CAR_SERVICE_PORT', 5002)}"

TEMP_RENTALS = [
    {
        "rental_id": "rental-550e8400-e29b-41d4-a716-446655440001",
        "user_id": "550e8400-e29b-41d4-a716-446655440001",
        "car_id": "car-550e8400-e29b-41d4-a716-446655440004",
        "start_date": datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0),
        "end_date": datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=3),
        "total_amount": 285.00,
        "status": "active",
        "pickup_location": "Vilnius Airport",
        "return_location": "Vilnius Airport",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=2),
        "updated_at": datetime.now(timezone.utc) - timedelta(hours=2)
    },
    {
        "rental_id": "rental-550e8400-e29b-41d4-a716-446655440002",
        "user_id": "550e8400-e29b-41d4-a716-446655440002",
        "car_id": "car-550e8400-e29b-41d4-a716-446655440001",
        "start_date": datetime.now(timezone.utc) - timedelta(days=7),
        "end_date": datetime.now(timezone.utc) - timedelta(days=5),
        "total_amount": 90.00,
        "status": "completed",
        "pickup_location": "Vilnius Center",
        "return_location": "Vilnius Center",
        "created_at": datetime.now(timezone.utc) - timedelta(days=8),
        "updated_at": datetime.now(timezone.utc) - timedelta(days=5)
    }
]


class Rental(BaseModel):
    rental_id: Optional[str] = None
    user_id: str
    car_id: str
    start_date: datetime
    end_date: datetime
    total_amount: float = Field(..., gt=0)
    status: str = Field(..., pattern="^(pending|active|completed|cancelled)$")
    pickup_location: str = Field(..., min_length=1, max_length=255)
    return_location: str = Field(..., min_length=1, max_length=255)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RentalCreate(BaseModel):
    user_id: str
    car_id: str
    start_date: datetime
    end_date: datetime
    pickup_location: str = Field(..., min_length=1, max_length=255)
    return_location: str = Field(..., min_length=1, max_length=255)


class RentalResponse(BaseModel):
    rental_id: str
    user_id: str
    car_id: str
    start_date: datetime
    end_date: datetime
    total_amount: float
    status: str
    pickup_location: str
    return_location: str
    created_at: datetime
    updated_at: datetime
    user_name: Optional[str] = None
    car_info: Optional[str] = None


async def get_user_info_from_azure(user_id: str) -> dict:
    """Get user information directly from Azure (not via HTTP)"""
    try:
        user_data = azure_client.get_user_by_id(user_id)
        if user_data:
            azure_client.log_to_azure("rental-service", "INFO", f"Found user {user_id} in Azure SQL")
        return user_data
    except Exception as e:
        azure_client.log_to_azure("rental-service", "WARN", f"Failed to get user from Azure: {e}")
        return None


async def get_car_info_from_azure(car_id: str) -> dict:
    """Get car information directly from Azure (not via HTTP)"""
    try:
        car_data = azure_client.get_car_by_id(car_id)
        if car_data:
            azure_client.log_to_azure("rental-service", "INFO", f"Found car {car_id} in Azure SQL")
        return car_data
    except Exception as e:
        azure_client.log_to_azure("rental-service", "WARN", f"Failed to get car from Azure: {e}")
        return None


async def update_car_status_in_azure(car_id: str, status: str) -> bool:
    """Update car status directly in Azure (not via HTTP)"""
    try:
        success = azure_client.update_car_status(car_id, status)
        if success:
            azure_client.log_to_azure("rental-service", "INFO", f"Updated car {car_id} status to {status} in Azure SQL")
        return success
    except Exception as e:
        azure_client.log_to_azure("rental-service", "WARN", f"Failed to update car status in Azure: {e}")
        return False


def calculate_total_amount(start_date: datetime, end_date: datetime, daily_rate: float) -> float:
    """Calculate total rental amount"""
    days = (end_date - start_date).days
    return (days if days > 0 else 1) * daily_rate


@app.get("/health")
async def health_check():
    """Health check endpoint with Azure connection info"""
    try:
        azure_client.log_to_azure("rental-service", "INFO", "Health check passed")

        azure_info = azure_client.get_connection_info()

        return {
            "status": "healthy",
            "service": "rental-service",
            "azure_connection": azure_info,
            "dependencies": {
                "user_service": USER_SERVICE_URL,
                "car_service": CAR_SERVICE_URL,
                "azure_direct_access": "enabled"
            },
            "timestamp": datetime.now(timezone.utc)
        }
    except Exception as e:
        azure_client.log_to_azure("rental-service", "ERROR", f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "rental-service",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc)
        }


@app.get("/ping")
async def ping():
    """Ping endpoint"""
    return {
        "message": "pong",
        "service": "rental-service",
        "timestamp": datetime.now(timezone.utc)
    }


@app.get("/metrics")
async def metrics():
    """Metrics endpoint with mixed data (Azure + in-memory)"""
    try:
        total_rentals = len(TEMP_RENTALS)
        status_counts = {}
        for status in ["active", "completed", "pending", "cancelled"]:
            status_counts[f"{status}_rentals"] = len([r for r in TEMP_RENTALS if r["status"] == status])

        total_revenue = sum(r["total_amount"] for r in TEMP_RENTALS if r["status"] == "completed")
        active_revenue = sum(r["total_amount"] for r in TEMP_RENTALS if r["status"] == "active")

        metrics_data = {
            "service": "rental-service",
            "timestamp": datetime.now(timezone.utc),
            "metrics": {
                "total_rentals": total_rentals,
                **status_counts,
                "total_revenue": total_revenue,
                "active_revenue": active_revenue,
                "average_rental_value": sum(
                    r["total_amount"] for r in TEMP_RENTALS) / total_rentals if total_rentals > 0 else 0,
                "status": "operational",
                "data_source": "mixed_azure_and_memory"
            }
        }

        azure_client.log_to_azure("rental-service", "INFO", "Metrics requested")
        return metrics_data

    except Exception as e:
        azure_client.log_to_azure("rental-service", "ERROR", f"Metrics endpoint failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")


@app.get("/rentals", response_model=List[RentalResponse])
async def get_all_rentals():
    """Get all rentals with Azure-enriched data"""
    try:
        rentals = []
        for rental_data in TEMP_RENTALS:
            user_info = await get_user_info_from_azure(rental_data["user_id"])
            car_info = await get_car_info_from_azure(rental_data["car_id"])

            rental = RentalResponse(
                **rental_data,
                user_name=f"{user_info['first_name']} {user_info['last_name']}" if user_info else "Unknown User",
                car_info=f"{car_info['make']} {car_info['model']} ({car_info['license_plate']})" if car_info else "Unknown Car"
            )
            rentals.append(rental)

        azure_client.log_to_azure("rental-service", "INFO", f"Retrieved {len(rentals)} rentals with Azure data")
        return rentals

    except Exception as e:
        azure_client.log_to_azure("rental-service", "ERROR", f"Failed to get rentals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve rentals: {str(e)}")


@app.get("/rentals/{rental_id}", response_model=RentalResponse)
async def get_rental(rental_id: str):
    """Get rental by ID with Azure-enriched data"""
    try:
        for rental_data in TEMP_RENTALS:
            if rental_data["rental_id"] == rental_id:
                user_info = await get_user_info_from_azure(rental_data["user_id"])
                car_info = await get_car_info_from_azure(rental_data["car_id"])

                rental = RentalResponse(
                    **rental_data,
                    user_name=f"{user_info['first_name']} {user_info['last_name']}" if user_info else "Unknown User",
                    car_info=f"{car_info['make']} {car_info['model']} ({car_info['license_plate']})" if car_info else "Unknown Car"
                )

                azure_client.log_to_azure("rental-service", "INFO", f"Retrieved rental {rental_id} with Azure data",
                                          rental_id)
                return rental

        raise HTTPException(status_code=404, detail="Rental not found")

    except HTTPException:
        raise
    except Exception as e:
        azure_client.log_to_azure("rental-service", "ERROR", f"Failed to get rental {rental_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve rental: {str(e)}")


@app.post("/rentals", response_model=RentalResponse)
async def create_rental(rental: RentalCreate):
    """Create new rental with Azure integration"""
    try:
        if rental.start_date.tzinfo is None:
            rental.start_date = rental.start_date.replace(tzinfo=timezone.utc)
        if rental.end_date.tzinfo is None:
            rental.end_date = rental.end_date.replace(tzinfo=timezone.utc)

        current_time = datetime.now(timezone.utc)

        if rental.end_date <= rental.start_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")

        if rental.start_date < current_time - timedelta(hours=1):
            raise HTTPException(status_code=400, detail="Start date cannot be in the past")

        user_info = await get_user_info_from_azure(rental.user_id)
        if not user_info:
            raise HTTPException(status_code=404, detail="User not found in Azure SQL")

        car_info = await get_car_info_from_azure(rental.car_id)
        if not car_info:
            raise HTTPException(status_code=404, detail="Car not found in Azure SQL")

        if car_info["status"] != "available":
            raise HTTPException(status_code=400, detail=f"Car is not available (status: {car_info['status']})")

        total_amount = calculate_total_amount(rental.start_date, rental.end_date, car_info["daily_rate"])

        rental_id = f"rental-{str(uuid.uuid4())}"
        new_rental_data = {
            "rental_id": rental_id,
            "user_id": rental.user_id,
            "car_id": rental.car_id,
            "start_date": rental.start_date,
            "end_date": rental.end_date,
            "total_amount": total_amount,
            "status": "pending",
            "pickup_location": rental.pickup_location,
            "return_location": rental.return_location,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        TEMP_RENTALS.append(new_rental_data)

        car_updated = await update_car_status_in_azure(rental.car_id, "rented")
        if not car_updated:
            azure_client.log_to_azure("rental-service", "WARN", f"Failed to update car status for rental {rental_id}")

        created_rental = RentalResponse(
            **new_rental_data,
            user_name=f"{user_info['first_name']} {user_info['last_name']}",
            car_info=f"{car_info['make']} {car_info['model']} ({car_info['license_plate']})"
        )

        azure_client.log_to_azure("rental-service", "INFO",
                                  f"Created new rental {rental_id} with Azure integration", rental_id)
        return created_rental

    except HTTPException:
        raise
    except Exception as e:
        azure_client.log_to_azure("rental-service", "ERROR", f"Failed to create rental: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create rental: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("RENTAL_SERVICE_PORT", 5003))
    azure_client.log_to_azure("rental-service", "INFO", f"Starting Rental Service on port {port}")
    print(f"🏠 Starting Rental Service with Azure integration on http://localhost:{port}")
    print(f"📚 API Documentation: http://localhost:{port}/docs")
    print(f"❤️  Health Check: http://localhost:{port}/health")
    uvicorn.run(app, host="0.0.0.0", port=port)