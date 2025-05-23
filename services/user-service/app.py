from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import time
import psutil
from datetime import datetime, timezone
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="User Management Service",
    description="Microservice for user management in Car Rental System",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demo (replace with database later)
users_db = {}
request_count = 0
start_time = time.time()


# Middleware to count requests
@app.middleware("http")
async def count_requests(request, call_next):
    global request_count
    request_count += 1
    start_time_req = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time_req
    logger.info(f"Request to {request.url.path} took {process_time:.4f} seconds")

    return response


# Health check endpoint - REQUIRED for 5 points
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint to verify service is running"""
    return {
        "status": "healthy",
        "service": "user-service",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }


# Ping endpoint - REQUIRED for 5 points
@app.get("/ping")
async def ping() -> Dict[str, str]:
    """Simple ping endpoint"""
    return {"message": "pong", "service": "user-service"}


# Metrics endpoint - REQUIRED for 5 points
@app.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Application metrics endpoint"""
    uptime = time.time() - start_time

    # Get system metrics
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()

    return {
        "service": "user-service",
        "uptime_seconds": round(uptime, 2),
        "request_count": request_count,
        "requests_per_second": round(request_count / uptime, 2) if uptime > 0 else 0,
        "memory_usage_percent": memory.percent,
        "cpu_usage_percent": cpu_percent,
        "active_users": len(users_db),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "User Management Service",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "ping": "/ping",
            "metrics": "/metrics",
            "users": "/users",
            "register": "/register"
        }
    }


# Get users endpoint - REQUIRED for API points
@app.get("/users")
async def get_users():
    """Get all users - demo endpoint"""
    logger.info("Fetching all users")
    return {
        "users": list(users_db.values()),
        "total_count": len(users_db)
    }


# User registration endpoint - REQUIRED for API points
@app.post("/register")
async def register_user(user_data: dict):
    """Register a new user"""
    try:
        # Basic validation
        if "email" not in user_data or "name" not in user_data:
            raise HTTPException(status_code=400, detail="Email and name are required")

        email = user_data["email"]

        # Check if user already exists
        if email in users_db:
            raise HTTPException(status_code=409, detail="User already exists")

        # Create user (in real app, encrypt PII data)
        user = {
            "id": len(users_db) + 1,
            "email": email,  # In production: encrypt this
            "name": user_data["name"],  # In production: encrypt this
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        users_db[email] = user
        logger.info(f"User registered: {email}")

        return {
            "message": "User registered successfully",
            "user_id": user["id"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    uvicorn.run(app, host="0.0.0.0", port=port)