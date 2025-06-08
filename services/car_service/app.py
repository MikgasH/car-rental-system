from fastapi import HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import uuid
from datetime import datetime
import sys
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
sys.path.insert(0, project_root)

from shared.cache import CacheService, car_cache
from services.car_service.database import CarDatabase

from azure.servicebus.aio import ServiceBusClient
import json
import asyncio
import threading

from shared.common import (
   create_service_app,
   run_service,
   ErrorHandler,
   DataValidator,
   ServiceLogger
)
from shared.encryption import encryptor, PII_FIELDS

db = CarDatabase()

SERVICE_BUS_CONNECTION_STR = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")
QUEUE_NAME = "car-status-queue"

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
   cars = db.get_all_cars()
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
   try:
       cached_cars = CacheService.get_all_cars()
       if cached_cars:
           ServiceLogger.log_operation("car-service", "get_all_cars", f"Retrieved {len(cached_cars)} cars from cache")
           return [CarResponse(**car_data) for car_data in cached_cars]

       cars_data = db.get_all_cars()
       decrypted_cars = [encryptor.decrypt_dict(car_data, PII_FIELDS['cars']) for car_data in cars_data]

       CacheService.set_all_cars(decrypted_cars, ttl=300)

       cars = [CarResponse(**car_data) for car_data in decrypted_cars]
       ServiceLogger.log_operation("car-service", "get_all_cars",
                                   f"Retrieved {len(cars)} cars from database and cached")
       return cars

   except Exception as e:
       ErrorHandler.handle_azure_error("car-service", "get_all_cars", e)


@app.get("/cars/{car_id}", response_model=CarResponse)
async def get_car(car_id: str):
   try:
       cached_car = CacheService.get_car(car_id)
       if cached_car:
           ServiceLogger.log_operation("car-service", "get_car", f"Retrieved car {car_id} from cache")
           return CarResponse(**cached_car)

       car_data = db.get_car_by_id(car_id)

       if not car_data:
           ErrorHandler.handle_not_found("car-service", "Car", car_id)

       decrypted_car_data = encryptor.decrypt_dict(car_data, PII_FIELDS['cars'])

       CacheService.set_car(car_id, decrypted_car_data, ttl=300)

       ServiceLogger.log_operation("car-service", "get_car", f"Retrieved car {car_id} from database and cached")
       return CarResponse(**decrypted_car_data)

   except HTTPException:
       raise
   except Exception as e:
       ErrorHandler.handle_azure_error("car-service", "get_car", e)


@app.get("/cars/available/{location}")
async def get_available_cars_by_location(location: str):
   try:
       cached_result = CacheService.get_available_cars(location)
       if cached_result:
           ServiceLogger.log_operation("car-service", "search_cars_by_location",
                                       f"Found {len(cached_result)} available cars in {location} from cache")
           return {
               "location": location,
               "available_cars": cached_result,
               "count": len(cached_result),
               "cached": True
           }

       all_cars = db.get_all_cars()
       available_cars = []

       for car_data in all_cars:
           if (car_data["status"] == "available" and
                   location.lower() in car_data["location"].lower()):
               decrypted_car = encryptor.decrypt_dict(car_data, PII_FIELDS['cars'])
               available_cars.append(CarResponse(**decrypted_car))

       available_cars_dict = [car.dict() for car in available_cars]

       CacheService.set_available_cars(location, available_cars_dict, ttl=120)

       ServiceLogger.log_operation("car-service", "search_cars_by_location",
                                   f"Found {len(available_cars)} available cars in {location} from database and cached")

       return {
           "location": location,
           "available_cars": available_cars,
           "count": len(available_cars),
           "cached": False
       }

   except Exception as e:
       ErrorHandler.handle_azure_error("car-service", "search_cars_by_location", e)


@app.get("/cars/status/{status}")
async def get_cars_by_status(status: str):
   try:
       if not DataValidator.validate_car_status(status):
           ErrorHandler.handle_validation_error("car-service",
                                                f"Invalid status. Use: available, rented, maintenance")

       cached_result = CacheService.get_cars_by_status(status)
       if cached_result:
           ServiceLogger.log_operation("car-service", "filter_cars_by_status",
                                       f"Found {len(cached_result)} cars with status {status} from cache")
           return {
               "status": status,
               "cars": cached_result,
               "count": len(cached_result),
               "cached": True
           }

       all_cars = db.get_all_cars()
       filtered_cars = []

       for car_data in all_cars:
           if car_data["status"] == status:
               decrypted_car = encryptor.decrypt_dict(car_data, PII_FIELDS['cars'])
               filtered_cars.append(CarResponse(**decrypted_car))

       filtered_cars_dict = [car.dict() for car in filtered_cars]

       CacheService.set_cars_by_status(status, filtered_cars_dict, ttl=180)

       ServiceLogger.log_operation("car-service", "filter_cars_by_status",
                                   f"Found {len(filtered_cars)} cars with status {status} from database and cached")

       return {
           "status": status,
           "cars": filtered_cars,
           "count": len(filtered_cars),
           "cached": False
       }

   except HTTPException:
       raise
   except Exception as e:
       ErrorHandler.handle_azure_error("car-service", "filter_cars_by_status", e)


@app.post("/cars", response_model=CarResponse)
async def create_car(car: CarCreate):
   try:
       existing_cars = [encryptor.decrypt_dict(c, PII_FIELDS['cars']) for c in db.get_all_cars()]
       if DataValidator.check_duplicate_license_plate(car.license_plate, existing_cars):
           ErrorHandler.handle_validation_error("car-service", "License plate already exists")

       new_car_data = {
           "car_id": str(uuid.uuid4()),
           "make": car.make,
           "model": car.model,
           "year": car.year,
           "license_plate": car.license_plate,
           "daily_rate": car.daily_rate,
           "location": car.location
       }
       encrypted_car_data_for_db = encryptor.encrypt_dict(new_car_data, PII_FIELDS['cars'])

       created_car_data = db.create_car(encrypted_car_data_for_db)
       decrypted_created_car = encryptor.decrypt_dict(created_car_data, PII_FIELDS['cars'])

       CacheService.set_car(created_car_data['car_id'], decrypted_created_car, ttl=300)
       CacheService.invalidate_car_cache()

       ServiceLogger.log_operation("car-service", "create_car",
                                   f"Created car {created_car_data['car_id']} and updated cache")

       return CarResponse(**decrypted_created_car)

   except HTTPException:
       raise
   except Exception as e:
       ErrorHandler.handle_azure_error("car-service", "create_car", e)


@app.put("/cars/{car_id}/status")
async def update_car_status(car_id: str, new_status: str):
   try:
       if not DataValidator.validate_car_status(new_status):
           ErrorHandler.handle_validation_error("car-service",
                                                f"Invalid status. Use: available, rented, maintenance")

       success = db.update_car_status(car_id, new_status)

       if not success:
           ErrorHandler.handle_not_found("car-service", "Car", car_id)

       updated_car_data = db.get_car_by_id(car_id)
       decrypted_updated_car = encryptor.decrypt_dict(updated_car_data, PII_FIELDS['cars'])

       CacheService.set_car(car_id, decrypted_updated_car, ttl=300)
       CacheService.invalidate_car_cache()

       ServiceLogger.log_operation("car-service", "update_car_status",
                                   f"Updated car {car_id} status to {new_status} and refreshed cache")

       return {
           "message": f"Car status updated to {new_status}",
           "car": CarResponse(**decrypted_updated_car)
       }

   except HTTPException:
       raise
   except Exception as e:
       ErrorHandler.handle_azure_error("car-service", "update_car_status", e)


@app.get("/cache/stats")
async def get_cache_stats():
   try:
       all_stats = CacheService.get_all_cache_stats()
       car_stats = all_stats["car_cache"]

       return {
           "service": "car-service",
           "cache_stats": car_stats,
           "cache_types": {
               "individual_cars": len([k for k in car_cache.get_keys() if k.startswith("car:")]),
               "all_cars": 1 if "all_cars" in car_cache.get_keys() else 0,
               "location_searches": len([k for k in car_cache.get_keys() if k.startswith("available_cars:")]),
               "status_filters": len([k for k in car_cache.get_keys() if k.startswith("cars_status:")])
           },
           "cached_operations": [
               "get_all_cars (TTL: 5min)",
               "get_car_by_id (TTL: 5min)",
               "get_available_cars_by_location (TTL: 2min)",
               "get_cars_by_status (TTL: 3min)"
           ],
           "invalidation_triggers": [
               "create_car",
               "update_car_status"
           ]
       }
   except Exception as e:
       return {"error": str(e), "service": "car-service"}


@app.get("/cache/clear")
async def clear_car_cache():
   try:
       entries_before = len(car_cache.get_keys())
       car_cache.clear()

       ServiceLogger.log_operation("car-service", "cache_clear", f"Cleared {entries_before} cache entries")

       return {
           "message": "Car service cache cleared successfully",
           "entries_cleared": entries_before,
           "service": "car-service"
       }
   except Exception as e:
       return {"error": str(e), "service": "car-service"}

async def receive_messages():
   ServiceLogger.log_operation("car-service", "servicebus_listener", "Starting Service Bus message listener...")
   try:
       servicebus_client = ServiceBusClient.from_connection_string(
           conn_str=SERVICE_BUS_CONNECTION_STR,
           logging_enable=True
       )
       async with servicebus_client:
           receiver = servicebus_client.get_queue_receiver(queue_name=QUEUE_NAME)
           async with receiver:
               while True:
                   received_msgs = await receiver.receive_messages(max_wait_time=5)
                   for message in received_msgs:
                       try:
                           message_body_str = str(message)
                           try:
                               message_body = json.loads(message_body_str)
                           except json.JSONDecodeError:
                               message_body = json.loads(message_body_str.decode('utf-8'))

                           ServiceLogger.log_operation(
                               "car-service", "servicebus_listener",
                               f"Received message: {message_body}"
                           )

                           event_type = message_body.get("event_type")
                           car_id = message_body.get("car_id")
                           new_status = message_body.get("new_status")

                           if event_type == "car_rented" and car_id and new_status == "rented":
                               ServiceLogger.log_operation(
                                   "car-service", "servicebus_listener",
                                   f"Processing 'car_rented' event for car_id: {car_id}"
                               )
                               success = db.update_car_status(car_id, new_status)
                               if success:
                                   ServiceLogger.log_operation(
                                       "car-service", "servicebus_listener",
                                       f"Successfully updated car {car_id} status to {new_status}"
                                   )
                                   await receiver.complete_message(message)
                               else:
                                   ServiceLogger.log_error(
                                       "car-service", "servicebus_listener",
                                       f"Failed to update car {car_id} status to {new_status} (car not found or DB error)"
                                   )
                                   await receiver.abandon_message(message)
                           else:
                               ServiceLogger.log_warning(
                                   "car-service", "servicebus_listener",
                                   f"Unknown event type or missing data: {message_body}. Completing message."
                               )
                               await receiver.complete_message(message)

                       except json.JSONDecodeError as jde:
                           ServiceLogger.log_error(
                               "car-service", "servicebus_listener",
                               f"Error decoding JSON from message: {jde}. Message body: {str(message)}. Completing message."
                           )
                           await receiver.complete_message(message)
                       except Exception as inner_e:
                           ServiceLogger.log_error(
                               "car-service", "servicebus_listener",
                               f"Error processing Service Bus message: {inner_e}"
                           )
                           await receiver.abandon_message(message)

                   await asyncio.sleep(0.1)


   except Exception as e:
       ServiceLogger.log_error("car-service", "servicebus_listener", f"Service Bus listener failed: {e}")


def start_servicebus_listener():
   asyncio.run(receive_messages())

@app.get("/test-logging")
async def test_azure_logging():
   import uuid

   test_user_id = str(uuid.uuid4())

   ServiceLogger.log_operation("car-service", "test_logging", "Testing Azure Storage and Service Bus logging",
                               test_user_id)
   ServiceLogger.log_warning("car-service", "test_logging", "Car inventory warning - low stock detected", test_user_id)
   ServiceLogger.log_error("car-service", "test_logging", "Car status update failed - database connection issue",
                           test_user_id)

   ServiceLogger.log_operation("car-service", "inventory_check", "Daily inventory validation completed")
   ServiceLogger.log_operation("car-service", "status_update", "Car availability status synchronized")
   ServiceLogger.log_operation("car-service", "service_bus_listener", "Message processing operational")

   return {
       "message": "Car Service Azure logging test completed successfully",
       "logs_sent_to": [
           "Azure Blob Storage (container: logs)",
           "Azure Service Bus (queue: application-logs)"
       ],
       "log_types_tested": ["INFO", "WARNING", "ERROR"],
       "car_service_operations": ["inventory_check", "status_update", "service_bus_listener"],
       "test_user_id": test_user_id,
       "storage_account": "carrentalstorage2025",
       "container": "logs",
       "queue": "application-logs",
       "service": "car-service",
       "status": "success"
   }


@app.get("/logs/recent")
async def get_recent_logs():
   try:
       from shared.azure_logger import azure_logger

       recent_logs = azure_logger.get_logs_from_storage("car-service", limit=10)

       return {
           "service": "car-service",
           "recent_logs_count": len(recent_logs),
           "logs": recent_logs[:5],
           "total_available": len(recent_logs),
           "storage_location": "Azure Blob Storage - carrentalstorage2025/logs",
           "service_operations": ["car inventory", "status updates", "service bus messaging"]
       }
   except Exception as e:
       return {
           "service": "car-service",
           "error": str(e),
           "message": "Could not retrieve logs from Azure Storage"
       }

if __name__ == "__main__":
   listener_thread = threading.Thread(target=start_servicebus_listener, daemon=True)
   listener_thread.start()

   run_service(app, "CAR", 5002)