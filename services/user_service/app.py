from fastapi import HTTPException
from pydantic import BaseModel, EmailStr, Field
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

service = create_service_app("User Service", "User management microservice")
app = service.get_app()

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)

class UserResponse(BaseModel):
    user_id: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

def get_user_metrics():
    """Get user-specific metrics"""
    users = azure_client.get_users()
    return {
        "total_users": len(users),
        "recent_registrations_24h": 0  # TODO: implement actual logic
    }

service.add_metrics_endpoint(get_user_metrics)

@app.get("/users", response_model=List[UserResponse])
async def get_all_users():
    """Get all users"""
    try:
        users_data = azure_client.get_users()
        users = [UserResponse(**user_data) for user_data in users_data]

        ServiceLogger.log_operation("user-service", "get_all_users", f"Retrieved {len(users)} users")
        return users

    except Exception as e:
        ErrorHandler.handle_azure_error("user-service", "get_all_users", e)

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    """Get user by ID"""
    try:
        user_data = azure_client.get_user_by_id(user_id)

        if not user_data:
            ErrorHandler.handle_not_found("user-service", "User", user_id)

        ServiceLogger.log_operation("user-service", "get_user", f"Retrieved user {user_id}", user_id)
        return UserResponse(**user_data)

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("user-service", "get_user", e)

@app.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate):
    """Create new user"""
    try:
        existing_users = azure_client.get_users()
        if DataValidator.check_duplicate_email(user.email, existing_users):
            ErrorHandler.handle_validation_error("user-service", "Email already registered")

        new_user_data = {
            "user_id": str(uuid.uuid4()),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "password_hash": "temp_hash_123"  # TODO: implement proper hashing
        }

        created_user_data = azure_client.create_user(new_user_data)

        ServiceLogger.log_operation("user-service", "create_user",
                                   f"Created user {created_user_data['user_id']}",
                                   created_user_data['user_id'])

        return UserResponse(**created_user_data)

    except HTTPException:
        raise
    except Exception as e:
        ErrorHandler.handle_azure_error("user-service", "create_user", e)

@app.get("/users/search/{email}")
async def search_user_by_email(email: str):
    """Search user by email"""
    try:
        all_users = azure_client.get_users()
        matching_users = []

        for user_data in all_users:
            if email.lower() in user_data["email"].lower():
                matching_users.append(UserResponse(**user_data))

        ServiceLogger.log_operation("user-service", "search_users",
                                   f"Email search '{email}' returned {len(matching_users)} results")

        return {
            "query": email,
            "results": matching_users,
            "count": len(matching_users)
        }

    except Exception as e:
        ErrorHandler.handle_azure_error("user-service", "search_users", e)

if __name__ == "__main__":
    run_service(app, "USER", 5001)