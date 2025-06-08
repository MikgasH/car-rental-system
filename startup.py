#!/usr/bin/env python3
"""
Azure App Service startup script
Запускает нужный микросервис на основе переменной SERVICE_TYPE
"""

import os
import sys


def start_service():
    service_type = os.getenv('SERVICE_TYPE', '').lower()

    print(f"🚀 Starting service: {service_type}")
    print(f"📂 Current directory: {os.getcwd()}")

    # Добавляем текущую директорию в Python path
    current_dir = os.getcwd()
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    if service_type == 'user':
        print("🔧 Starting User Service...")
        # Переходим в папку user_service
        user_service_path = os.path.join(current_dir, 'services', 'user_service')
        os.chdir(user_service_path)

        # Добавляем путь к shared модулям
        shared_path = os.path.join(current_dir, 'shared')
        if shared_path not in sys.path:
            sys.path.insert(0, shared_path)

        # Импортируем и запускаем приложение
        from app import app
        import uvicorn

        port = int(os.getenv('PORT', 8000))
        print(f"🌐 Starting on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)

    elif service_type == 'car':
        print("🔧 Starting Car Service...")
        car_service_path = os.path.join(current_dir, 'services', 'car_service')
        os.chdir(car_service_path)

        shared_path = os.path.join(current_dir, 'shared')
        if shared_path not in sys.path:
            sys.path.insert(0, shared_path)

        from app import app
        import uvicorn

        port = int(os.getenv('PORT', 8000))
        print(f"🌐 Starting on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)

    elif service_type == 'rental':
        print("🔧 Starting Rental Service...")
        rental_service_path = os.path.join(current_dir, 'services', 'rental_service')
        os.chdir(rental_service_path)

        shared_path = os.path.join(current_dir, 'shared')
        if shared_path not in sys.path:
            sys.path.insert(0, shared_path)

        from app import app
        import uvicorn

        port = int(os.getenv('PORT', 8000))
        print(f"🌐 Starting on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)

    else:
        print(f"❌ Unknown SERVICE_TYPE: '{service_type}'")
        print("💡 Available types: user, car, rental")
        print("🔍 Check your environment variables!")
        sys.exit(1)


if __name__ == "__main__":
    print("🎯 Azure App Service startup script")
    print("=" * 50)
    start_service()