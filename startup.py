import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_environment():
    """Validate required environment variables."""
    service_type = os.getenv('SERVICE_TYPE', '').lower()
    if not service_type:
        logger.error("SERVICE_TYPE environment variable not set")
        return False

    if service_type not in ['user', 'car', 'rental']:
        logger.error(f"Invalid SERVICE_TYPE: {service_type}")
        return False

    return True


def setup_python_path(base_dir):
    """Setup Python path for proper module imports."""
    paths_to_add = [
        base_dir,
        os.path.join(base_dir, 'shared')
    ]

    for path in paths_to_add:
        if os.path.exists(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added to Python path: {path}")


def verify_service_structure(base_dir, service_type):
    """Verify that service directory structure exists."""
    service_path = os.path.join(base_dir, 'services', f'{service_type}_service')

    if not os.path.exists(service_path):
        logger.error(f"Service directory not found: {service_path}")
        return False

    app_file = os.path.join(service_path, 'app.py')
    if not os.path.exists(app_file):
        logger.error(f"App file not found: {app_file}")
        return False

    logger.info(f"Service structure verified: {service_path}")
    return True


def start_service():
    """Main service startup logic."""
    try:
        if not validate_environment():
            sys.exit(1)

        service_type = os.getenv('SERVICE_TYPE').lower()
        logger.info(f"Starting {service_type} service")

        base_dir = os.getcwd()
        logger.info(f"Base directory: {base_dir}")

        setup_python_path(base_dir)

        if not verify_service_structure(base_dir, service_type):
            sys.exit(1)

        service_path = os.path.join(base_dir, 'services', f'{service_type}_service')

        if service_path not in sys.path:
            sys.path.insert(0, service_path)

        os.chdir(service_path)
        logger.info(f"Changed working directory to: {service_path}")

        logger.info("Importing application modules")
        from app import app
        import uvicorn

        port = int(os.getenv('PORT', 8000))
        host = "0.0.0.0"

        logger.info(f"Starting uvicorn server on {host}:{port}")

        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True
        )

    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    logger.info("Azure App Service startup script initialized")
    start_service()