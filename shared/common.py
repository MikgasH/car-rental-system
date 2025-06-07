from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Dict, Any
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class BaseService:
    """Base class for all microservices"""

    def __init__(self, service_name: str, service_description: str = None):
        self.service_name = service_name
        self.app = FastAPI(
            title=service_name,
            version="1.0.0",
            description=service_description or f"{service_name} microservice"
        )
        self._setup_common_endpoints()

    def _setup_common_endpoints(self):
        """Setup common endpoints for all services"""

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            try:
                return {
                    "status": "healthy",
                    "service": self.service_name.lower(),
                    "timestamp": datetime.now(timezone.utc)
                }
            except Exception as e:
                return {
                    "status": "unhealthy",
                    "service": self.service_name.lower(),
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc)
                }

        @self.app.get("/ping")
        async def ping():
            """Ping endpoint"""
            return {
                "message": "pong",
                "service": self.service_name.lower(),
                "timestamp": datetime.now(timezone.utc)
            }

    def add_metrics_endpoint(self, metrics_callback):
        """Add metrics endpoint with custom callback"""

        @self.app.get("/metrics")
        async def metrics():
            """Service metrics endpoint"""
            try:
                custom_metrics = metrics_callback()

                metrics_data = {
                    "service": self.service_name.lower(),
                    "timestamp": datetime.now(timezone.utc),
                    "metrics": {
                        **custom_metrics,
                        "status": "operational",
                        "data_source": "azure_sql_database"
                    }
                }

                return metrics_data

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")

    def get_app(self):
        """Get FastAPI app instance"""
        return self.app


class ServiceResponse(BaseModel):
    """Standard service response format"""
    success: bool
    message: str
    data: Any = None
    timestamp: datetime = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now(timezone.utc)
        super().__init__(**data)


class ErrorHandler:
    """Common error handling utilities"""

    @staticmethod
    def handle_azure_error(service_name: str, operation: str, error: Exception):
        """Handle Azure-related errors"""
        error_msg = f"Azure operation failed in {operation}: {str(error)}"
        print(f"ERROR [{service_name}]: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Database operation failed: {str(error)}")

    @staticmethod
    def handle_not_found(service_name: str, resource_type: str, resource_id: str):
        """Handle resource not found errors"""
        error_msg = f"{resource_type} {resource_id} not found"
        print(f"WARN [{service_name}]: {error_msg}")
        raise HTTPException(status_code=404, detail=f"{resource_type} not found")

    @staticmethod
    def handle_validation_error(service_name: str, validation_msg: str):
        """Handle validation errors"""
        print(f"WARN [{service_name}]: Validation error: {validation_msg}")
        raise HTTPException(status_code=400, detail=validation_msg)


class DataValidator:
    """Common data validation utilities"""

    @staticmethod
    def check_duplicate_email(email: str, existing_users: list, exclude_user_id: str = None):
        """Check for duplicate email addresses"""
        for user in existing_users:
            if user["email"] == email and user.get("user_id") != exclude_user_id:
                return True
        return False

    @staticmethod
    def check_duplicate_license_plate(license_plate: str, existing_cars: list, exclude_car_id: str = None):
        """Check for duplicate license plates"""
        for car in existing_cars:
            if car["license_plate"] == license_plate and car.get("car_id") != exclude_car_id:
                return True
        return False

    @staticmethod
    def validate_car_status(status: str):
        """Validate car status"""
        valid_statuses = ["available", "rented", "maintenance"]
        return status in valid_statuses

    @staticmethod
    def validate_rental_status(status: str):
        """Validate rental status"""
        valid_statuses = ["pending", "active", "completed", "cancelled"]
        return status in valid_statuses


class ServiceLogger:
    """Service-specific logging utilities"""

    @staticmethod
    def log_operation(service_name: str, operation: str, details: str = None, user_id: str = None):
        """Log service operation"""
        message = f"{operation}"
        if details:
            message += f": {details}"
        print(f"INFO [{service_name}]: {message}" + (f" (user: {user_id})" if user_id else ""))

    @staticmethod
    def log_error(service_name: str, operation: str, error: str, user_id: str = None):
        """Log service error"""
        message = f"{operation} failed: {error}"
        print(f"ERROR [{service_name}]: {message}" + (f" (user: {user_id})" if user_id else ""))

    @staticmethod
    def log_warning(service_name: str, operation: str, warning: str, user_id: str = None):
        """Log service warning"""
        message = f"{operation} warning: {warning}"
        print(f"WARN [{service_name}]: {message}" + (f" (user: {user_id})" if user_id else ""))


def create_service_app(service_name: str, description: str = None):
    """Factory function to create standardized service app"""
    service = BaseService(service_name, description)
    return service


def run_service(app: FastAPI, service_name: str, default_port: int):
    """Standard service runner"""
    import uvicorn

    port = int(os.getenv(f"{service_name.upper()}_SERVICE_PORT", default_port))

    ServiceLogger.log_operation(service_name.lower(), "service_startup", f"Starting on port {port}")

    print(f"Starting {service_name} on http://localhost:{port}")
    print(f"API Documentation: http://localhost:{port}/docs")
    print(f"Health Check: http://localhost:{port}/health")

    uvicorn.run(app, host="0.0.0.0", port=port)


def success_response(message: str, data: Any = None):
    """Create successful response"""
    return ServiceResponse(success=True, message=message, data=data)


def error_response(message: str, data: Any = None):
    """Create error response"""
    return ServiceResponse(success=False, message=message, data=data)