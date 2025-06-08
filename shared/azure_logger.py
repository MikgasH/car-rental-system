# shared/azure_logger.py
import os
import json
import asyncio
import threading
from datetime import datetime, timezone
from queue import Queue
from azure.storage.blob import BlobServiceClient
from azure.servicebus import ServiceBusClient, ServiceBusMessage


class AzureLogger:
    """Azure Storage and Service Bus logger for car rental system"""

    def __init__(self):
        self.storage_connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.servicebus_connection_string = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")

        self.container_name = "logs"
        self.log_queue_name = "application-logs"

        self.log_queue = Queue()
        self.processing_thread = None
        self.running = False

        self._init_azure_clients()

    def _init_azure_clients(self):
        """Initialize Azure Storage and Service Bus clients"""
        try:
            if self.storage_connection_string:
                self.blob_client = BlobServiceClient.from_connection_string(
                    self.storage_connection_string
                )
                self._ensure_container_exists()
                print("✓ Azure Storage logger initialized")

            if self.servicebus_connection_string:
                self.servicebus_client = ServiceBusClient.from_connection_string(
                    self.servicebus_connection_string
                )
                print("✓ Azure Service Bus logger initialized")

        except Exception as e:
            print(f"Warning: Azure logger initialization failed: {e}")

    def _ensure_container_exists(self):
        """Create logs container if it doesn't exist"""
        try:
            container_client = self.blob_client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container()
                print(f"✓ Created logs container: {self.container_name}")
        except Exception as e:
            print(f"Warning: Could not create logs container: {e}")

    def start_processing(self):
        """Start background thread for log processing"""
        if not self.processing_thread or not self.processing_thread.is_alive():
            self.running = True
            self.processing_thread = threading.Thread(
                target=self._process_logs_background,
                daemon=True
            )
            self.processing_thread.start()
            print("✓ Azure logger background processing started")

    def stop_processing(self):
        """Stop background processing"""
        self.running = False
        if self.processing_thread:
            self.processing_thread.join(timeout=2)

    def _process_logs_background(self):
        """Background thread to process log queue"""
        while self.running:
            try:
                if not self.log_queue.empty():
                    log_entry = self.log_queue.get(timeout=1)
                    self._send_to_azure(log_entry)
                else:
                    threading.Event().wait(0.1)
            except Exception as e:
                print(f"Log processing error: {e}")

    def log_operation(self, service_name: str, operation: str, details: str = None,
                      user_id: str = None, level: str = "INFO"):
        """Log service operation to Azure Storage and Service Bus"""
        timestamp = datetime.now(timezone.utc)

        log_entry = {
            "timestamp": timestamp.isoformat(),
            "service_name": service_name,
            "level": level,
            "operation": operation,
            "details": details,
            "user_id": user_id,
            "log_id": f"{service_name}-{int(timestamp.timestamp() * 1000)}"
        }

        console_msg = f"{level} [{service_name}]: {operation}"
        if details:
            console_msg += f": {details}"
        if user_id:
            console_msg += f" (user: {user_id})"
        print(console_msg)

        self.log_queue.put(log_entry)

        if not self.running:
            self.start_processing()

    def log_error(self, service_name: str, operation: str, error: str, user_id: str = None):
        """Log error to Azure"""
        self.log_operation(service_name, operation, error, user_id, "ERROR")

    def log_warning(self, service_name: str, operation: str, warning: str, user_id: str = None):
        """Log warning to Azure"""
        self.log_operation(service_name, operation, warning, user_id, "WARN")

    def _send_to_azure(self, log_entry: dict):
        """Send log entry to Azure Storage and Service Bus"""
        try:
            if hasattr(self, 'blob_client'):
                self._send_to_blob_storage(log_entry)

            if hasattr(self, 'servicebus_client'):
                self._send_to_service_bus(log_entry)

        except Exception as e:
            print(f"Failed to send log to Azure: {e}")

    def _send_to_blob_storage(self, log_entry: dict):
        """Upload log to Azure Blob Storage"""
        try:
            date_str = datetime.now().strftime('%Y-%m-%d')
            blob_name = f"{date_str}/{log_entry['service_name']}/{log_entry['log_id']}.json"

            blob_client = self.blob_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )

            log_data = json.dumps(log_entry, indent=2)
            blob_client.upload_blob(
                log_data,
                overwrite=True,
                metadata={
                    "service": log_entry["service_name"],
                    "level": log_entry["level"],
                    "operation": log_entry["operation"]
                }
            )

        except Exception as e:
            print(f"Failed to upload log to blob storage: {e}")

    def _send_to_service_bus(self, log_entry: dict):
        """Send log to Service Bus for real-time processing"""
        try:
            # Create sender for log queue
            sender = self.servicebus_client.get_queue_sender(self.log_queue_name)

            # Create message with properties
            message_body = json.dumps(log_entry)
            message = ServiceBusMessage(
                message_body,
                application_properties={
                    "service": log_entry["service_name"],
                    "level": log_entry["level"],
                    "timestamp": log_entry["timestamp"]
                }
            )

            sender.send_messages(message)
            sender.close()

        except Exception as e:
            print(f"Failed to send log to Service Bus: {e}")

    def get_logs_from_storage(self, service_name: str = None, date: str = None, limit: int = 100):
        """Retrieve logs from Azure Storage (for debugging/monitoring)"""
        try:
            container_client = self.blob_client.get_container_client(self.container_name)

            prefix = ""
            if date:
                prefix += f"{date}/"
            if service_name:
                prefix += f"{service_name}/"

            blobs = container_client.list_blobs(name_starts_with=prefix)

            logs = []
            count = 0
            for blob in blobs:
                if count >= limit:
                    break

                blob_client = container_client.get_blob_client(blob.name)
                content = blob_client.download_blob().readall()
                log_entry = json.loads(content)
                logs.append(log_entry)
                count += 1

            return logs

        except Exception as e:
            print(f"Failed to retrieve logs from storage: {e}")
            return []


azure_logger = AzureLogger()


def log_to_azure(service_name: str, operation: str, details: str = None, user_id: str = None, level: str = "INFO"):
    """Convenient function for logging to Azure"""
    azure_logger.log_operation(service_name, operation, details, user_id, level)


def log_error_to_azure(service_name: str, operation: str, error: str, user_id: str = None):
    """Convenient function for error logging to Azure"""
    azure_logger.log_error(service_name, operation, error, user_id)


def log_warning_to_azure(service_name: str, operation: str, warning: str, user_id: str = None):
    """Convenient function for warning logging to Azure"""
    azure_logger.log_warning(service_name, operation, warning, user_id)