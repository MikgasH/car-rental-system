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

from shared.cache import CacheService, user_cache
from services.user_service.database import UserDatabase

from shared.common import (
   create_service_app,
   run_service,
   ErrorHandler,
   DataValidator,
   ServiceLogger
)
from shared.encryption import encryptor, PII_FIELDS

db = UserDatabase()

service = create_service_app("User Service", "User management microservice")
app = service.get_app()


class UserCreate(BaseModel):
   first_name: str = Field(..., min_length=1, max_length=50)
   last_name: str = Field(..., min_length=1, max_length=50)
   email: str = Field(..., min_length=1, max_length=100)
   phone: str = Field(..., min_length=1, max_length=20)


class UserResponse(BaseModel):
   user_id: str
   first_name: str
   last_name: str
   email: str
   phone: str
   created_at: datetime
   updated_at: datetime


def get_user_metrics():
   users = db.get_all_users()
   total_users = len(users)

   return {
       "total_users": total_users,
       "active_users": total_users
   }

service.add_metrics_endpoint(get_user_metrics)


@app.get("/users", response_model=List[UserResponse])
async def get_all_users():
   try:
       cached_users = CacheService.get_all_users()
       if cached_users:
           ServiceLogger.log_operation("user-service", "get_all_users",
                                       f"Retrieved {len(cached_users)} users from cache")
           return [UserResponse(**user_data) for user_data in cached_users]

       users_data = db.get_all_users()
       decrypted_users = [encryptor.decrypt_dict(user_data, PII_FIELDS['users']) for user_data in users_data]

       CacheService.set_all_users(decrypted_users, ttl=300)

       users = [UserResponse(**user_data) for user_data in decrypted_users]
       ServiceLogger.log_operation("user-service", "get_all_users",
                                   f"Retrieved {len(users)} users from database and cached")
       return users

   except Exception as e:
       ErrorHandler.handle_azure_error("user-service", "get_all_users", e)


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
   try:
       cached_user = CacheService.get_user(user_id)
       if cached_user:
           ServiceLogger.log_operation("user-service", "get_user", f"Retrieved user {user_id} from cache")
           return UserResponse(**cached_user)

       user_data = db.get_user_by_id(user_id)

       if not user_data:
           ErrorHandler.handle_not_found("user-service", "User", user_id)

       decrypted_user_data = encryptor.decrypt_dict(user_data, PII_FIELDS['users'])

       CacheService.set_user(user_id, decrypted_user_data, ttl=600)

       ServiceLogger.log_operation("user-service", "get_user", f"Retrieved user {user_id} from database and cached")
       return UserResponse(**decrypted_user_data)

   except HTTPException:
       raise
   except Exception as e:
       ErrorHandler.handle_azure_error("user-service", "get_user", e)


@app.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate):
   try:
       existing_users = [encryptor.decrypt_dict(u, PII_FIELDS['users']) for u in db.get_all_users()]
       if DataValidator.check_duplicate_email(user.email, existing_users):
           ErrorHandler.handle_validation_error("user-service", "Email already exists")

       new_user_data = {
           "user_id": str(uuid.uuid4()),
           "first_name": user.first_name,
           "last_name": user.last_name,
           "email": user.email,
           "phone": user.phone,
       }

       encrypted_user_data_for_db = encryptor.encrypt_dict(new_user_data, PII_FIELDS['users'])
       created_user_data = db.create_user(encrypted_user_data_for_db)

       decrypted_created_user = encryptor.decrypt_dict(created_user_data, PII_FIELDS['users'])

       CacheService.set_user(created_user_data['user_id'], decrypted_created_user, ttl=600)
       CacheService.invalidate_user(None)

       ServiceLogger.log_operation("user-service", "create_user",
                                   f"Created user {created_user_data['user_id']} and updated cache")

       return UserResponse(**decrypted_created_user)

   except HTTPException:
       raise
   except Exception as e:
       ErrorHandler.handle_azure_error("user-service", "create_user", e)


@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user: UserCreate):
   try:
       user_data_from_db = db.get_user_by_id(user_id)
       if not user_data_from_db:
           ErrorHandler.handle_not_found("user-service", "User", user_id)

       existing_users = [encryptor.decrypt_dict(u, PII_FIELDS['users']) for u in db.get_all_users()]
       if DataValidator.check_duplicate_email(user.email, existing_users, exclude_user_id=user_id):
           ErrorHandler.handle_validation_error("user-service", "Email already exists for another user")

       updated_user_data = {
           "first_name": user.first_name,
           "last_name": user.last_name,
           "email": user.email,
           "phone": user.phone,
       }
       encrypted_updated_user_data_for_db = encryptor.encrypt_dict(updated_user_data, PII_FIELDS['users'])

       success = db.update_user(user_id, encrypted_updated_user_data_for_db)

       if not success:
           ErrorHandler.handle_not_found("user-service", "User", user_id)

       final_user_data = db.get_user_by_id(user_id)
       decrypted_final_user = encryptor.decrypt_dict(final_user_data, PII_FIELDS['users'])

       CacheService.set_user(user_id, decrypted_final_user, ttl=600)
       CacheService.invalidate_user(None)

       ServiceLogger.log_operation("user-service", "update_user",
                                   f"Updated user {user_id} and refreshed cache")

       return UserResponse(**decrypted_final_user)

   except HTTPException:
       raise
   except Exception as e:
       ErrorHandler.handle_azure_error("user-service", "update_user", e)


@app.delete("/users/{user_id}")
async def delete_user(user_id: str):
   try:
       success = db.delete_user(user_id)

       if not success:
           ErrorHandler.handle_not_found("user-service", "User", user_id)

       CacheService.invalidate_user(user_id)

       ServiceLogger.log_operation("user-service", "delete_user",
                                   f"Deleted user {user_id} and invalidated cache")
       return {"message": "User deleted successfully"}

   except HTTPException:
       raise
   except Exception as e:
       ErrorHandler.handle_azure_error("user-service", "delete_user", e)


@app.get("/cache/stats")
async def get_cache_stats():
   try:
       all_stats = CacheService.get_all_cache_stats()
       user_stats = all_stats["user_cache"]

       return {
           "service": "user-service",
           "cache_stats": user_stats,
           "cache_keys": len([k for k in user_cache.get_keys() if k.startswith("user:")]),
           "cached_operations": [
               "get_all_users (TTL: 5min)",
               "get_user_by_id (TTL: 10min)"
           ],
           "invalidation_triggers": [
               "create_user",
               "update_user",
               "delete_user"
           ]
       }
   except Exception as e:
       return {"error": str(e), "service": "user-service"}


@app.get("/cache/clear")
async def clear_user_cache():
   try:
       from shared.cache import user_cache
       entries_before = len(user_cache.get_keys())
       user_cache.clear()

       ServiceLogger.log_operation("user-service", "cache_clear", f"Cleared {entries_before} cache entries")

       return {
           "message": "User service cache cleared successfully",
           "entries_cleared": entries_before,
           "service": "user-service"
       }
   except Exception as e:
       return {"error": str(e), "service": "user-service"}

@app.get("/test-logging")
async def test_azure_logging():
   import uuid

   test_user_id = str(uuid.uuid4())

   ServiceLogger.log_operation("user-service", "test_logging", "Testing Azure Storage and Service Bus logging",
                               test_user_id)
   ServiceLogger.log_warning("user-service", "test_logging", "This is a test warning message", test_user_id)
   ServiceLogger.log_error("user-service", "test_logging", "This is a test error message", test_user_id)

   ServiceLogger.log_operation("user-service", "health_check", "Azure logging system operational")
   ServiceLogger.log_operation("user-service", "metrics_generated", "System metrics collected")

   return {
       "message": "Azure logging test completed successfully",
       "logs_sent_to": [
           "Azure Blob Storage (container: logs)",
           "Azure Service Bus (queue: application-logs)"
       ],
       "log_types_tested": ["INFO", "WARNING", "ERROR"],
       "test_user_id": test_user_id,
       "storage_account": "carrentalstorage2025",
       "container": "logs",
       "queue": "application-logs",
       "status": "success"
   }


@app.get("/logs/recent")
async def get_recent_logs():
   try:
       from shared.azure_logger import azure_logger

       recent_logs = azure_logger.get_logs_from_storage("user-service", limit=10)

       return {
           "service": "user-service",
           "recent_logs_count": len(recent_logs),
           "logs": recent_logs,
           "storage_location": "Azure Blob Storage - carrentalstorage2025/logs"
       }
   except Exception as e:
       return {
           "service": "user-service",
           "error": str(e),
           "message": "Could not retrieve logs from Azure Storage"
       }

if __name__ == "__main__":
   run_service(app, "USER", 5001)