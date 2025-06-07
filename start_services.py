import subprocess
import sys
import time
import os
from pathlib import Path


def start_service(service_name, port, script_path):
    """Launching a single service"""
    try:
        print(f"🚀 Starting {service_name} on port {port}...")

        if not os.path.exists(script_path):
            print(f"✗ File not found: {script_path}")
            return None

        service_dir = os.path.dirname(script_path)
        script_name = os.path.basename(script_path)

        print(f"📁 Working directory: {service_dir}")
        print(f"📄 Script: {script_name}")

        process = subprocess.Popen([
            sys.executable, script_name
        ], cwd=service_dir)

        print(f"✓ {service_name} started with PID {process.pid}")
        return process
    except Exception as e:
        print(f"✗ Failed to start {service_name}: {e}")
        return None


def main():
    """The main function of launching all services"""
    print("🏁 Car Rental System - Starting All Services")
    print("=" * 50)

    services = []
    processes = []

    service_configs = [
        {
            "name": "User Service",
            "port": 5001,
            "path": "services/user_service/app.py",
            "url": "http://localhost:5001"
        },
        {
            "name": "Car Service",
            "port": 5002,
            "path": "services/car_service/app.py",
            "url": "http://localhost:5002"
        },
        {
            "name": "Rental Service",
            "port": 5003,
            "path": "services/rental_service/app.py",
            "url": "http://localhost:5003"
        }
    ]

    for config in service_configs:
        if Path(config["path"]).exists():
            process = start_service(config["name"], config["port"], config["path"])
            if process:
                processes.append({
                    "process": process,
                    "name": config["name"],
                    "url": config["url"]
                })
                services.append(config)
        else:
            print(f"💥  {config['name']} not found at {config['path']}")

    if not processes:
        print("✗ No services could be started!")
        return

    print("\n🎯 Services Overview:")
    print("-" * 30)
    for service in services:
        print(f"• {service['name']}: {service['url']}")
        print(f"  Health: {service['url']}/health")
        print(f"  Docs: {service['url']}/docs")

    print(f"\n✓ Started {len(processes)} service(s)")
    print("📱 Press Ctrl+C to stop all services")

    try:
        while True:
            time.sleep(1)
            for p in processes[:]:
                if p["process"].poll() is not None:
                    print(f"💀 {p['name']} stopped unexpectedly")
                    processes.remove(p)

            if not processes:
                print("✗ All services stopped")
                break

    except KeyboardInterrupt:
        print("\n🛑 Stopping all services...")
        for p in processes:
            try:
                p["process"].terminate()
                print(f"✓ Stopped {p['name']}")
            except:
                pass
        print("All services stopped")


if __name__ == "__main__":
    main()