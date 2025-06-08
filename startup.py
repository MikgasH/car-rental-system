#!/usr/bin/env python3
"""
Azure App Service startup script - FIXED PATHS VERSION
"""

import os
import sys
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def start_service():
    try:
        service_type = os.getenv('SERVICE_TYPE', '').lower()
        logger.info(f"🚀 Starting service: {service_type}")

        # Получаем текущую директорию (где находится startup.py)
        current_dir = os.getcwd()
        logger.info(f"📂 Current directory: {current_dir}")

        # Показываем содержимое директории для отладки
        logger.info(f"📋 Directory contents: {os.listdir(current_dir)}")

        # Добавляем текущую директорию в Python path
        if current_dir not in sys.path:
            sys.path.insert(0, current_dir)

        # Добавляем папку shared в Python path
        shared_path = os.path.join(current_dir, 'shared')
        if os.path.exists(shared_path) and shared_path not in sys.path:
            sys.path.insert(0, shared_path)
            logger.info(f"✅ Added shared path: {shared_path}")

        if service_type == 'user':
            logger.info("🔧 Starting User Service...")

            # Проверяем структуру папок
            services_path = os.path.join(current_dir, 'services')
            user_service_path = os.path.join(services_path, 'user_service')

            logger.info(f"🔍 Looking for services at: {services_path}")
            if os.path.exists(services_path):
                logger.info(f"📂 Services contents: {os.listdir(services_path)}")
            else:
                logger.error(f"❌ Services directory not found: {services_path}")
                return

            logger.info(f"🔍 Looking for user_service at: {user_service_path}")
            if os.path.exists(user_service_path):
                logger.info(f"📂 User service contents: {os.listdir(user_service_path)}")

                # Добавляем путь к user_service в sys.path
                if user_service_path not in sys.path:
                    sys.path.insert(0, user_service_path)

                # Переходим в папку user_service
                os.chdir(user_service_path)
                logger.info(f"📁 Changed directory to: {os.getcwd()}")

                # Проверяем что app.py существует
                app_file = os.path.join(user_service_path, 'app.py')
                if os.path.exists(app_file):
                    logger.info("✅ app.py found!")
                else:
                    logger.error(f"❌ app.py not found at: {app_file}")
                    return

                # Импортируем приложение
                logger.info("📦 Importing FastAPI app...")
                from app import app
                import uvicorn

                # Запускаем сервер
                port = int(os.getenv('PORT', 8000))
                logger.info(f"🌐 Starting server on port {port}")

                uvicorn.run(
                    app,
                    host="0.0.0.0",
                    port=port,
                    log_level="info"
                )

            else:
                logger.error(f"❌ User service directory not found: {user_service_path}")
                logger.info(f"💡 Try checking if 'services' folder exists in: {current_dir}")
                return

        elif service_type == 'car':
            logger.info("🔧 Starting Car Service...")
            car_service_path = os.path.join(current_dir, 'services', 'car_service')

            if os.path.exists(car_service_path):
                sys.path.insert(0, car_service_path)
                os.chdir(car_service_path)

                from app import app
                import uvicorn

                port = int(os.getenv('PORT', 8000))
                uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
            else:
                logger.error(f"❌ Car service not found: {car_service_path}")
                return

        elif service_type == 'rental':
            logger.info("🔧 Starting Rental Service...")
            rental_service_path = os.path.join(current_dir, 'services', 'rental_service')

            if os.path.exists(rental_service_path):
                sys.path.insert(0, rental_service_path)
                os.chdir(rental_service_path)

                from app import app
                import uvicorn

                port = int(os.getenv('PORT', 8000))
                uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
            else:
                logger.error(f"❌ Rental service not found: {rental_service_path}")
                return

        else:
            logger.error(f"❌ Unknown SERVICE_TYPE: '{service_type}'")
            logger.info("💡 Available types: user, car, rental")
            logger.info("🔍 Current environment variables:")
            for key, value in os.environ.items():
                if 'SERVICE' in key:
                    logger.info(f"  {key}: {value}")
            return

    except Exception as e:
        logger.error(f"💥 Startup error: {str(e)}")
        import traceback
        logger.error(f"📋 Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    logger.info("🎯 Azure App Service startup script")
    logger.info("=" * 50)
    start_service()