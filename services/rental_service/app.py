import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import uuid
from datetime import datetime, timedelta
import sys

current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from shared.cache import CacheService, rental_cache
from services.rental_service.database import RentalDatabase
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
import json
import asyncio

from shared.common import (
    create_service_app,
    run_service,
    ErrorHandler,
    DataValidator,
    ServiceLogger
)
from shared.encryption import encryptor, PII_FIELDS

db = RentalDatabase()

SERVICE_BUS_CONNECTION_STR = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
QUEUE_NAME = "car-status-queue"

service = create_service_app("Rental Service", "Car rental management microservice")
app = service.get_app()


class RentalCreate(BaseModel):
    user_id: str = Field(..., min_length=1)
    car_id: str = Field(..., min_length=1)
    start_date: datetime
    end_date: datetime
    pickup_location: str = Field(..., min_length=1, max_length=100)
    return_location: str = Field(..., min_length=1, max_length=100)


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


async def send_message_to_servicebus(event_data: dict):
    if not SERVICE_BUS_CONNECTION_STR:
        ServiceLogger.log_error("rental-service", "send_message_to_servicebus", "Service Bus connection string is not set.")
        return

    try:
        servicebus_client = ServiceBusClient.from_connection_string(SERVICE_BUS_CONNECTION_STR)
        sender = servicebus_client.get_queue_sender(queue_name=QUEUE_NAME)
        async with sender:
            message = ServiceBusMessage(json.dumps(event_data))
            await sender.send_messages(message)
            ServiceLogger.log_operation("rental-service", "send_message_to_servicebus", f"Sent message: {event_data}")
    except Exception as e:
        ServiceLogger.log_error("rental-service", "send_message_to_servicebus", f"Failed to send message to Service Bus: {e}")


def get_rental_metrics():
    cached_metrics = CacheService.get_rental_metrics()
    if cached_metrics:
        return cached_metrics

    rentals = db.get_all_rentals()
    total_rentals = len(rentals)
    active_rentals = len([r for r in rentals if r["status"] == "active"])
    completed_rentals = len([r for r in rentals if r["status"] == "completed"])
    pending_rentals = len([r for r in rentals if r["status"] == "pending"])
    cancelled_rentals = len([r for r in rentals if r["status"] == "cancelled"])
    total_revenue = sum(r["total_amount"] for r in rentals if r["status"] == "completed")

    metrics = {
        "total_rentals": total_rentals,
        "active_rentals": active_rentals,
        "completed_rentals": completed_rentals,
        "pending_rentals": pending_rentals,
        "cancelled_rentals": cancelled_rentals,
        "total_revenue": total_revenue
    }

    CacheService.set_rental_metrics(metrics, ttl=60)
    return metrics


service.add_metrics_endpoint(get_rental_metrics)


async def fetch_user_data(user_id: str):
    try:
        user_service_url = os.getenv("USER_SERVICE_URL", "http://localhost:5001")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{user_service_url}/users/{user_id}")
            response.raise_for_status()
            user_data = response.json()
            return encryptor.decrypt_dict(user_data, PII_FIELDS['users'])
    except httpx.RequestError as exc:
        ServiceLogger.log_error("rental-service", "fetch_user_data", f"Error fetching user data for {user_id}: {exc}")
        return None
    except httpx.HTTPStatusError as exc:
        ServiceLogger.log_error("rental-service", "fetch_user_data", f"User service returned error for {user_id}: {exc.response.status_code} - {exc.response.text}")
        return None
    except Exception as e:
        ServiceLogger.log_error("rental-service", "fetch_user_data", f"An unexpected error occurred while fetching user data for {user_id}: {e}")
        return None


async def fetch_car_data(car_id: str):
    try:
        car_service_url = os.getenv("CAR_SERVICE_URL", "http://localhost:5002")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{car_service_url}/cars/{car_id}")
            response.raise_for_status()
            car_data = response.json()
            return encryptor.decrypt_dict(car_data, PII_FIELDS['cars'])
    except httpx.RequestError as exc:
        ServiceLogger.log_error("rental-service", "fetch_car_data", f"Error fetching car data for {car_id}: {exc}")
        return None
    except httpx.HTTPStatusError as exc:
        ServiceLogger.log_error("rental-service", "fetch_car_data", f"Car service returned error for {car_id}: {exc.response.status_code} - {exc.response.text}")
        return None
    except Exception as e:
        ServiceLogger.log_error("rental-service", "fetch_car_data", f"An unexpected error occurred while fetching car data for {car_id}: {e}")
        return None


@app.get("/rentals", response_model=List[RentalResponse])
async def get_all_rentals():
    try:
        cached_rentals = CacheService.get_all_rentals()
        if cached_rentals:
            ServiceLogger.log_operation("rental-service", "get_all_rentals",
                                        f"Retrieved {len(cached_rentals)} rentals from cache")
            return [RentalResponse(**rental_data) for rental_data in cached_rentals]

        rentals_data = db.get_all_rentals()
        rentals = []

        for rental_data in rentals_data:
            decrypted_rental = encryptor.decrypt_dict(rental_data, PII_FIELDS['rentals'])
            rental_obj = RentalResponse(**decrypted_rental)

            user_data = await fetch_user_data(rental_obj.user_id)
            if user_data:
                rental_obj.user_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()

            car_data = await fetch_car_data(rental_obj.car_id)
            if car_data:
                rental_obj.car_info = f"{car_data.get('make', '')} {car_data.get('model', '')} ({car_data.get('license_plate', '')})".strip()

            rentals.append(rental_obj)

        rentals_dict = [rental.dict() for rental in rentals]
        CacheService.set_all_rentals(rentals_dict, ttl=180)

        ServiceLogger.log_operation("rental-service", "get_all_rentals",
                                    f"Retrieved {len(rentals)} rentals from database and cached")
        return rentals

    except Exception as e:
        ErrorHandler.handle_azure_error("rental-service", "get_all_rentals", e)


@app.get("/rentals/{rental_id}", response_model=RentalResponse)
async def get_rental(rental_id: str):
    try:
        cached_rental = CacheService.get_rental(rental_id)
        if cached_rental:
            ServiceLogger.log_operation("rental-service", "get_rental", f"Retrieved rental {rental_id} from cache")
            return RentalResponse(**cached_rental)

        rental_data = db.get_rental_by_id(rental_id)
        if not rental_data:
            ErrorHandler.handle_not_found("rental-service", "Rental", rental_id)

        decrypted_rental = encryptor.decrypt_dict(rental_data, PII_FIELDS['rentals'])
        rental_obj = RentalResponse(**decrypted_rental)

        user_data = await fetch_user_data(rental_obj.user_id)
        if user_data:
            rental_obj.user_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()

        car_data = await fetch_car_data(rental_obj.car_id)
        if car_data:
            rental_obj.car_info = f"{car_data.get('make', '')} {car_data.get('model', '')} ({car_data.get('license_plate', '')})".strip()

        CacheService.set_rental(rental_id, rental_obj.dict(), ttl=180)

        ServiceLogger.log_operation("rental-service", "get_rental",
                                    f"Retrieved rental {rental_id} from database and cached")
        return rental_obj

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("rental-service", "get_rental", e)


@app.post("/rentals", response_model=RentalResponse)
async def create_rental(rental: RentalCreate):
    try:
        if rental.start_date >= rental.end_date:
            ErrorHandler.handle_validation_error("rental-service", "End date must be after start date")

        user_data = await fetch_user_data(rental.user_id)
        if not user_data:
            ErrorHandler.handle_not_found("rental-service", "User", rental.user_id)

        car_data = await fetch_car_data(rental.car_id)
        if not car_data:
            ErrorHandler.handle_not_found("rental-service", "Car", rental.car_id)
        if car_data["status"] != "available":
            ErrorHandler.handle_validation_error("rental-service", f"Car {car_data['license_plate']} is not available for rent.")

        duration = (rental.end_date - rental.start_date).days
        if duration == 0:
            duration = 1
        total_amount = duration * car_data["daily_rate"]

        new_rental_data = {
            "rental_id": str(uuid.uuid4()),
            "user_id": rental.user_id,
            "car_id": rental.car_id,
            "start_date": rental.start_date,
            "end_date": rental.end_date,
            "total_amount": total_amount,
            "status": "pending",
            "pickup_location": rental.pickup_location,
            "return_location": rental.return_location
        }

        encrypted_rental_data_for_db = encryptor.encrypt_dict(new_rental_data, PII_FIELDS['rentals'])
        created_rental_data = db.create_rental(encrypted_rental_data_for_db)

        event_data = {
            "event_type": "car_rented",
            "car_id": rental.car_id,
            "rental_id": created_rental_data["rental_id"],
            "new_status": "rented"
        }
        await send_message_to_servicebus(event_data)

        CacheService.invalidate_rental_cache()

        ServiceLogger.log_operation("rental-service", "create_rental",
                                    f"Created rental {created_rental_data['rental_id']} and invalidated cache")

        decrypted_rental = encryptor.decrypt_dict(created_rental_data, PII_FIELDS['rentals'])
        rental_obj = RentalResponse(**decrypted_rental)

        if user_data:
            rental_obj.user_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
        if car_data:
            rental_obj.car_info = f"{car_data.get('make', '')} {car_data.get('model', '')} ({car_data.get('license_plate', '')})".strip()

        CacheService.set_rental(created_rental_data["rental_id"], rental_obj.dict(), ttl=180)

        return rental_obj

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("rental-service", "create_rental", e)


@app.put("/rentals/{rental_id}/status")
async def update_rental_status(rental_id: str, new_status: str):
    try:
        if not DataValidator.validate_rental_status(new_status):
            ErrorHandler.handle_validation_error("rental-service",
                                                 f"Invalid status. Use: pending, active, completed, cancelled")

        success = db.update_rental_status(rental_id, new_status)

        if not success:
            ErrorHandler.handle_not_found("rental-service", "Rental", rental_id)

        updated_rental_data = db.get_rental_by_id(rental_id)
        decrypted_rental = encryptor.decrypt_dict(updated_rental_data, PII_FIELDS['rentals'])
        rental_obj = RentalResponse(**decrypted_rental)

        user_data = await fetch_user_data(rental_obj.user_id)
        if user_data:
            rental_obj.user_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()

        car_data = await fetch_car_data(rental_obj.car_id)
        if car_data:
            rental_obj.car_info = f"{car_data.get('make', '')} {car_data.get('model', '')} ({car_data.get('license_plate', '')})".strip()

        CacheService.set_rental(rental_id, rental_obj.dict(), ttl=180)
        CacheService.invalidate_rental_cache()

        ServiceLogger.log_operation("rental-service", "update_rental_status",
                                    f"Updated rental {rental_id} status to {new_status} and refreshed cache")

        return {
            "message": f"Rental status updated to {new_status}",
            "rental": rental_obj
        }

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("rental-service", "update_rental_status", e)


@app.get("/cache/stats")
async def get_cache_stats():
    try:
        all_stats = CacheService.get_all_cache_stats()
        rental_stats = all_stats["rental_cache"]

        return {
            "service": "rental-service",
            "cache_stats": rental_stats,
            "cache_types": {
                "individual_rentals": len([k for k in rental_cache.get_keys() if k.startswith("rental:")]),
                "all_rentals": 1 if "all_rentals" in rental_cache.get_keys() else 0,
                "metrics": 1 if "rental_metrics" in rental_cache.get_keys() else 0
            },
            "cached_operations": [
                "get_all_rentals (TTL: 3min)",
                "get_rental_by_id (TTL: 3min)",
                "get_rental_metrics (TTL: 1min)"
            ],
            "invalidation_triggers": [
                "create_rental",
                "update_rental_status"
            ]
        }
    except Exception as e:
        return {"error": str(e), "service": "rental-service"}


@app.get("/cache/clear")
async def clear_rental_cache():
    try:
        entries_before = len(rental_cache.get_keys())
        rental_cache.clear()

        ServiceLogger.log_operation("rental-service", "cache_clear", f"Cleared {entries_before} cache entries")

        return {
            "message": "Rental service cache cleared successfully",
            "entries_cleared": entries_before,
            "service": "rental-service"
        }
    except Exception as e:
        return {"error": str(e), "service": "rental-service"}


@app.get("/cache/global-stats")
async def get_global_cache_stats():
    try:
        all_stats = CacheService.get_all_cache_stats()

        return {
            "system": "car-rental-microservices",
            "cache_overview": {
                "total_cache_entries": all_stats["total_cache_entries"],
                "services": {
                    "user_service": {
                        "entries": all_stats["user_cache"]["total_entries"],
                        "hit_rate": all_stats["user_cache"]["hit_rate_percent"],
                        "requests": all_stats["user_cache"]["total_requests"]
                    },
                    "car_service": {
                        "entries": all_stats["car_cache"]["total_entries"],
                        "hit_rate": all_stats["car_cache"]["hit_rate_percent"],
                        "requests": all_stats["car_cache"]["total_requests"]
                    },
                    "rental_service": {
                        "entries": all_stats["rental_cache"]["total_entries"],
                        "hit_rate": all_stats["rental_cache"]["hit_rate_percent"],
                        "requests": all_stats["rental_cache"]["total_requests"]
                    }
                }
            },
            "detailed_stats": all_stats
        }
    except Exception as e:
        return {"error": str(e), "system": "car-rental-microservices"}


@app.get("/test-logging")
async def test_azure_logging():
    test_user_id = str(uuid.uuid4())
    test_rental_id = str(uuid.uuid4())

    ServiceLogger.log_operation("rental-service", "test_logging", "Testing Azure Storage and Service Bus logging",
                                test_user_id)
    ServiceLogger.log_warning("rental-service", "test_logging", "Rental validation warning - date conflict detected",
                              test_user_id)
    ServiceLogger.log_error("rental-service", "test_logging",
                            "Payment processing failed - external service unavailable", test_user_id)

    ServiceLogger.log_operation("rental-service", "rental_created", f"New rental booking created: {test_rental_id}",
                                test_user_id)
    ServiceLogger.log_operation("rental-service", "cross_service_validation", "User and car validation completed")
    ServiceLogger.log_operation("rental-service", "service_bus_message", "Car status update message sent to queue")
    ServiceLogger.log_operation("rental-service", "business_logic",
                                "Rental amount calculation and date validation completed")

    return {
        "message": "Rental Service Azure logging test completed successfully",
        "logs_sent_to": [
            "Azure Blob Storage (container: logs)",
            "Azure Service Bus (queue: application-logs)"
        ],
        "log_types_tested": ["INFO", "WARNING", "ERROR"],
        "rental_service_operations": [
            "rental_created",
            "cross_service_validation",
            "service_bus_message",
            "business_logic"
        ],
        "test_user_id": test_user_id,
        "test_rental_id": test_rental_id,
        "storage_account": "carrentalstorage2025",
        "container": "logs",
        "queue": "application-logs",
        "service": "rental-service",
        "status": "success"
    }


@app.get("/logs/recent")
async def get_recent_logs():
    try:
        from shared.azure_logger import azure_logger

        recent_logs = azure_logger.get_logs_from_storage("rental-service", limit=10)

        return {
            "service": "rental-service",
            "recent_logs_count": len(recent_logs),
            "logs": recent_logs[:5],
            "total_available": len(recent_logs),
            "storage_location": "Azure Blob Storage - carrentalstorage2025/logs",
            "service_operations": [
                "rental management",
                "cross-service integration",
                "service bus messaging",
                "business logic validation"
            ]
        }
    except Exception as e:
        return {
            "service": "rental-service",
            "error": str(e),
            "message": "Could not retrieve logs from Azure Storage"
        }


if __name__ == "__main__":
    run_service(app, "RENTAL", 5003)