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
    """Get user-specific metrics"""
    users = db.get_all_users()
    total_users = len(users)

    return {
        "total_users": total_users,
        "active_users": total_users
    }

service.add_metrics_endpoint(get_user_metrics)


@app.get("/users", response_model=List[UserResponse])
async def get_all_users():
    """Get all users"""
    try:
        users_data = db.get_all_users()
        decrypted_users = [encryptor.decrypt_dict(user_data, PII_FIELDS['users']) for user_data in users_data]
        users = [UserResponse(**user_data) for user_data in decrypted_users]

        ServiceLogger.log_operation("user-service", "get_all_users", f"Retrieved {len(users)} users")
        return users

    except Exception as e:
        ErrorHandler.handle_azure_error("user-service", "get_all_users", e)


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    """Get user by ID"""
    try:
        user_data = db.get_user_by_id(user_id)

        if not user_data:
            ErrorHandler.handle_not_found("user-service", "User", user_id)

        decrypted_user_data = encryptor.decrypt_dict(user_data, PII_FIELDS['users'])

        ServiceLogger.log_operation("user-service", "get_user", f"Retrieved user {user_id}")
        return UserResponse(**decrypted_user_data)

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("user-service", "get_user", e)


@app.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate):
    """Create new user"""
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

        ServiceLogger.log_operation("user-service", "create_user",
                                    f"Created user {created_user_data['user_id']}")

        return UserResponse(**encryptor.decrypt_dict(created_user_data, PII_FIELDS['users']))

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("user-service", "create_user", e)


@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user: UserCreate):
    """Update existing user"""
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

        ServiceLogger.log_operation("user-service", "update_user",
                                    f"Updated user {user_id}")

        return UserResponse(**encryptor.decrypt_dict(final_user_data, PII_FIELDS['users']))

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("user-service", "update_user", e)


@app.delete("/users/{user_id}")
async def delete_user(user_id: str):
    """Delete a user"""
    try:
        success = db.delete_user(user_id)

        if not success:
            ErrorHandler.handle_not_found("user-service", "User", user_id)

        ServiceLogger.log_operation("user-service", "delete_user",
                                    f"Deleted user {user_id}")
        return {"message": "User deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("user-service", "delete_user", e)

@app.get("/test-logging")
async def test_azure_logging():
    """Test endpoint to demonstrate Azure logging functionality"""
    import uuid

    test_user_id = str(uuid.uuid4())

    # Test different log levels
    ServiceLogger.log_operation("user-service", "test_logging", "Testing Azure Storage and Service Bus logging",
                                test_user_id)
    ServiceLogger.log_warning("user-service", "test_logging", "This is a test warning message", test_user_id)
    ServiceLogger.log_error("user-service", "test_logging", "This is a test error message", test_user_id)

    # Test real operations logging
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
    """Get recent logs from Azure Storage for monitoring"""
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