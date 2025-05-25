from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
import os
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from azure_database_client import azure_client

load_dotenv()

app = FastAPI(title="User Service", version="1.0.0")


class User(BaseModel):
    user_id: Optional[str] = None
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        azure_client.log_to_azure("user-service", "INFO", "Health check passed")

        azure_info = azure_client.get_connection_info()

        return {
            "status": "healthy",
            "service": "user-service",
            "azure_connection": azure_info,
            "timestamp": datetime.now(timezone.utc)
        }
    except Exception as e:
        azure_client.log_to_azure("user-service", "ERROR", f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "service": "user-service",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc)
        }


@app.get("/ping")
async def ping():
    """Ping endpoint"""
    return {
        "message": "pong",
        "service": "user-service",
        "timestamp": datetime.now(timezone.utc)
    }


@app.get("/metrics")
async def metrics():
    """Metrics endpoint with Azure data"""
    try:
        users = azure_client.get_users()
        user_count = len(users)

        metrics_data = {
            "service": "user-service",
            "timestamp": datetime.now(timezone.utc),
            "metrics": {
                "total_users": user_count,
                "recent_registrations_24h": 0,  # TODO: реальная логика
                "status": "operational",
                "data_source": "azure_sql_database"
            }
        }

        azure_client.log_to_azure("user-service", "INFO", "Metrics requested")
        return metrics_data

    except Exception as e:
        azure_client.log_to_azure("user-service", "ERROR", f"Metrics endpoint failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")


@app.get("/users", response_model=List[UserResponse])
async def get_all_users():
    """Get all users from Azure SQL Database"""
    try:
        users_data = azure_client.get_users()
        users = [UserResponse(**user_data) for user_data in users_data]

        azure_client.log_to_azure("user-service", "INFO", f"Retrieved {len(users)} users from Azure SQL")
        return users
    except Exception as e:
        azure_client.log_to_azure("user-service", "ERROR", f"Failed to get users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve users: {str(e)}")


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    """Get user by ID from Azure SQL Database"""
    try:
        user_data = azure_client.get_user_by_id(user_id)

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        user = UserResponse(**user_data)
        azure_client.log_to_azure("user-service", "INFO", f"Retrieved user {user_id} from Azure SQL", user_id)
        return user

    except HTTPException:
        raise
    except Exception as e:
        azure_client.log_to_azure("user-service", "ERROR", f"Failed to get user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve user: {str(e)}")


@app.post("/users", response_model=UserResponse)
async def create_user(user: UserCreate):
    """Create new user in Azure SQL Database"""
    try:
        existing_users = azure_client.get_users()
        for existing_user in existing_users:
            if existing_user["email"] == user.email:
                raise HTTPException(status_code=400, detail="Email already registered")

        user_id = str(uuid.uuid4())
        new_user_data = {
            "user_id": user_id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone
        }

        created_user_data = azure_client.create_user(new_user_data)
        created_user = UserResponse(**created_user_data)

        azure_client.log_to_azure("user-service", "INFO", f"Created new user {user_id} in Azure SQL", user_id)
        return created_user

    except HTTPException:
        raise
    except Exception as e:
        azure_client.log_to_azure("user-service", "ERROR", f"Failed to create user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")


@app.get("/users/search/{email}")
async def search_user_by_email(email: str):
    """Search user by email in Azure SQL Database"""
    try:
        all_users = azure_client.get_users()
        matching_users = []

        for user_data in all_users:
            if email.lower() in user_data["email"].lower():
                user = UserResponse(**user_data)
                matching_users.append(user)

        azure_client.log_to_azure("user-service", "INFO",
                                  f"Search by email '{email}' returned {len(matching_users)} results from Azure SQL")
        return {"query": email, "results": matching_users, "count": len(matching_users)}

    except Exception as e:
        azure_client.log_to_azure("user-service", "ERROR", f"Failed to search users by email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("USER_SERVICE_PORT", 5001))
    azure_client.log_to_azure("user-service", "INFO", f"Starting User Service on port {port}")
    print(f"🚀 Starting User Service with Azure SQL on http://localhost:{port}")
    print(f"📚 API Documentation: http://localhost:{port}/docs")
    print(f"❤️  Health Check: http://localhost:{port}/health")
    uvicorn.run(app, host="0.0.0.0", port=port)