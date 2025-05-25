from fastapi import HTTPException, FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import uuid
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from azure_database_client import azure_client

load_dotenv()

app = FastAPI(
    title="Rental Service",
    version="1.0.0",
    description="Rental management and booking microservice"
)

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

def get_rentals_from_azure():
    """Get all rentals from Azure SQL"""
    try:
        conn = azure_client._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rental_id, user_id, car_id, start_date, end_date, 
                   total_amount, status, pickup_location, return_location, 
                   created_at, updated_at
            FROM Rentals ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        rentals = []
        for row in rows:
            rentals.append({
                "rental_id": str(row.rental_id),
                "user_id": str(row.user_id),
                "car_id": str(row.car_id),
                "start_date": row.start_date,
                "end_date": row.end_date,
                "total_amount": float(row.total_amount),
                "status": row.status,
                "pickup_location": row.pickup_location,
                "return_location": row.return_location,
                "created_at": row.created_at,
                "updated_at": row.updated_at
            })
        conn.close()
        return rentals
    except Exception as e:
        ServiceLogger.log_error("rental-service", "get_rentals_from_azure", str(e))
        return []

def get_rental_by_id_from_azure(rental_id: str):
    """Get specific rental from Azure SQL"""
    try:
        conn = azure_client._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rental_id, user_id, car_id, start_date, end_date, 
                   total_amount, status, pickup_location, return_location, 
                   created_at, updated_at
            FROM Rentals WHERE rental_id = ?
        """, (rental_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "rental_id": str(row.rental_id),
                "user_id": str(row.user_id),
                "car_id": str(row.car_id),
                "start_date": row.start_date,
                "end_date": row.end_date,
                "total_amount": float(row.total_amount),
                "status": row.status,
                "pickup_location": row.pickup_location,
                "return_location": row.return_location,
                "created_at": row.created_at,
                "updated_at": row.updated_at
            }
        return None
    except Exception:
        return None

def get_rental_metrics():
    """Get rental metrics"""
    try:
        rentals = get_rentals_from_azure()
        total_rentals = len(rentals)
        status_counts = {}
        for status in ["active", "completed", "pending", "cancelled"]:
            status_counts[f"{status}_rentals"] = len([r for r in rentals if r["status"] == status])

        return {
            "total_rentals": total_rentals,
            **status_counts,
            "total_revenue": sum(r["total_amount"] for r in rentals if r["status"] == "completed"),
            "active_revenue": sum(r["total_amount"] for r in rentals if r["status"] == "active"),
        }
    except Exception:
        return {"total_rentals": 0, "active_rentals": 0, "completed_rentals": 0, "pending_rentals": 0, "cancelled_rentals": 0}

@app.get("/health")
async def health_check():
    """Health check with dependencies - EXACT MATCH to old code"""
    try:
        ServiceLogger.log_operation("rental-service", "health_check", "Health check requested")
        azure_info = azure_client.get_connection_info()

        return {
            "status": "healthy",
            "service": "rental-service",
            "azure_connection": azure_info,
            "dependencies": {
                "user_service": f"http://localhost:{os.getenv('USER_SERVICE_PORT', 5001)}",
                "car_service": f"http://localhost:{os.getenv('CAR_SERVICE_PORT', 5002)}",
                "azure_direct_access": "enabled"
            },
            "timestamp": datetime.now(timezone.utc)
        }
    except Exception as e:
        ServiceLogger.log_error("rental-service", "health_check", str(e))
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
    """Service metrics endpoint"""
    try:
        custom_metrics = get_rental_metrics()

        metrics_data = {
            "service": "rental-service",
            "timestamp": datetime.now(timezone.utc),
            "metrics": {
                **custom_metrics,
                "status": "operational",
                "data_source": "azure_sql_database"
            }
        }

        ServiceLogger.log_operation("rental-service", "metrics", "Metrics requested")
        return metrics_data

    except Exception as e:
        ServiceLogger.log_error("rental-service", "metrics", f"Metrics endpoint failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")

@app.get("/rentals", response_model=List[RentalResponse])
async def get_all_rentals():
    """Get all rentals"""
    try:
        rentals_data = get_rentals_from_azure()
        rentals = []
        for rental_data in rentals_data:
            try:
                user_info = azure_client.get_user_by_id(rental_data["user_id"])
                car_info = azure_client.get_car_by_id(rental_data["car_id"])
                rental = RentalResponse(
                    **rental_data,
                    user_name=f"{user_info['first_name']} {user_info['last_name']}" if user_info else "Unknown User",
                    car_info=f"{car_info['make']} {car_info['model']} ({car_info['license_plate']})" if car_info else "Unknown Car"
                )
            except:
                rental = RentalResponse(**rental_data, user_name="Unknown User", car_info="Unknown Car")
            rentals.append(rental)
        return rentals
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rentals/{rental_id}", response_model=RentalResponse)
async def get_rental(rental_id: str):
    """Get rental by ID"""
    rental_data = get_rental_by_id_from_azure(rental_id)
    if not rental_data:
        raise HTTPException(status_code=404, detail="Rental not found")

    try:
        user_info = azure_client.get_user_by_id(rental_data["user_id"])
        car_info = azure_client.get_car_by_id(rental_data["car_id"])
        return RentalResponse(
            **rental_data,
            user_name=f"{user_info['first_name']} {user_info['last_name']}" if user_info else "Unknown User",
            car_info=f"{car_info['make']} {car_info['model']} ({car_info['license_plate']})" if car_info else "Unknown Car"
        )
    except:
        return RentalResponse(**rental_data, user_name="Unknown User", car_info="Unknown Car")

@app.post("/rentals", response_model=RentalResponse)
async def create_rental(rental: RentalCreate):
    """Create new rental"""
    try:
        if rental.start_date.tzinfo is None:
            rental.start_date = rental.start_date.replace(tzinfo=timezone.utc)
        if rental.end_date.tzinfo is None:
            rental.end_date = rental.end_date.replace(tzinfo=timezone.utc)

        if rental.start_date >= rental.end_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")

        current_time = datetime.now(timezone.utc)
        if rental.start_date < current_time - timedelta(hours=1):
            raise HTTPException(status_code=400, detail="Start date cannot be in the past")

        try:
            user_info = azure_client.get_user_by_id(rental.user_id)
            if not user_info:
                raise HTTPException(status_code=404, detail="User not found")
        except Exception:
            raise HTTPException(status_code=404, detail="User not found")

        try:
            car_info = azure_client.get_car_by_id(rental.car_id)
            if not car_info:
                raise HTTPException(status_code=404, detail="Car not found")
        except Exception:
            raise HTTPException(status_code=404, detail="Car not found")

        if car_info.get("status") != "available":
            raise HTTPException(status_code=400, detail=f"Car is not available")

        rental_id = str(uuid.uuid4())
        days = max(1, (rental.end_date - rental.start_date).days)
        total_amount = days * car_info.get("daily_rate", 50.0)

        conn = azure_client._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Rentals (
                rental_id, user_id, car_id, start_date, end_date,
                total_amount, status, pickup_location, return_location
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rental_id, rental.user_id, rental.car_id,
            rental.start_date, rental.end_date, total_amount,
            "pending", rental.pickup_location, rental.return_location
        ))
        conn.commit()
        conn.close()

        created_rental_data = get_rental_by_id_from_azure(rental_id)
        if not created_rental_data:
            raise HTTPException(status_code=500, detail="Failed to create rental")

        return RentalResponse(
            **created_rental_data,
            user_name=f"{user_info['first_name']} {user_info['last_name']}",
            car_info=f"{car_info['make']} {car_info['model']} ({car_info['license_plate']})"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    from shared.common import ServiceLogger

    port = int(os.getenv("RENTAL_SERVICE_PORT", 5003))
    ServiceLogger.log_operation("rental-service", "service_startup", f"Starting on port {port}")

    print(f"Starting RENTAL on http://localhost:{port}")
    print(f"Health Check: http://localhost:{port}/health")

    uvicorn.run(app, host="0.0.0.0", port=port)