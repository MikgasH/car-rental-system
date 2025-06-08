#!/usr/bin/env python3
"""
Car Rental System - Test Suite Runner
Validates microservices functionality and Azure integration
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import time


class TestRunner:
    """Professional test runner for car rental microservices"""

    def __init__(self):
        self.start_time = time.time()
        self.results = {}

    def setup_environment(self):
        """Load and validate environment configuration"""
        env_file = Path(".env")
        if not env_file.exists():
            print("ERROR: .env file not found")
            return False

        load_dotenv(env_file)

        required_vars = [
            "ENCRYPTION_KEY",
            "USER_DATABASE_CONNECTION_STRING",
            "CAR_DATABASE_CONNECTION_STRING",
            "RENTAL_DATABASE_CONNECTION_STRING"
        ]

        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            print(f"ERROR: Missing environment variables: {', '.join(missing)}")
            return False

        return True

    def check_dependencies(self):
        """Verify required Python packages are installed"""
        required_imports = [
            ("pytest", "pytest"),
            ("fastapi", "fastapi"),
            ("httpx", "httpx"),
            ("cryptography", "cryptography"),
            ("python-dotenv", "dotenv")  # dotenv is the import name
        ]

        missing = []
        for package_name, import_name in required_imports:
            try:
                __import__(import_name)
            except ImportError:
                missing.append(package_name)

        if missing:
            print(f"ERROR: Missing packages: {', '.join(missing)}")
            print("Install with: pip install " + " ".join(missing))
            return False

        return True

    def run_test_suite(self, test_file):
        """Execute test suite for a service"""
        if not Path(test_file).exists():
            return {"status": "NOT_FOUND", "details": "File not found"}

        cmd = [
            sys.executable, "-m", "pytest",
            test_file,
            "-v",
            "--tb=short",
            "--strict-markers",
            "--disable-warnings"
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                passed = result.stdout.count(" PASSED")
                skipped = result.stdout.count(" SKIPPED")
                return {
                    "status": "PASSED",
                    "passed": passed,
                    "skipped": skipped,
                    "details": f"{passed} passed, {skipped} skipped"
                }
            else:
                failed = result.stdout.count(" FAILED")
                errors = result.stdout.count(" ERROR")
                return {
                    "status": "FAILED",
                    "failed": failed,
                    "errors": errors,
                    "details": self._extract_error_details(result.stdout)
                }

        except subprocess.TimeoutExpired:
            return {"status": "TIMEOUT", "details": "Execution timeout"}
        except Exception as e:
            return {"status": "ERROR", "details": str(e)}

    def _extract_error_details(self, stdout):
        """Extract concise error information from test output"""
        lines = stdout.split('\n')
        errors = []

        for line in lines:
            if "FAILED" in line and "::" in line:
                test_name = line.split("::")[-1].split()[0]
                errors.append(test_name)

        return f"Failed tests: {', '.join(errors[:3])}" if errors else "Test failures detected"

    def validate_azure_configuration(self):
        """Validate Azure resource configuration"""
        checks = {
            "Azure SQL": self._check_azure_sql(),
            "Service Bus": self._check_service_bus(),
            "Storage": self._check_storage(),
            "Encryption": self._check_encryption()
        }

        return checks

    def _check_azure_sql(self):
        """Verify Azure SQL Database configuration"""
        conn_str = os.getenv("USER_DATABASE_CONNECTION_STRING", "")
        return "car-rental-sql-server.database.windows.net" in conn_str

    def _check_service_bus(self):
        """Verify Azure Service Bus configuration"""
        conn_str = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING", "")
        return "car-rental-servicebus.servicebus.windows.net" in conn_str

    def _check_storage(self):
        """Verify Azure Storage configuration"""
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
        return "carrentalstorage2025" in conn_str

    def _check_encryption(self):
        """Verify encryption key configuration"""
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            return False
        try:
            from cryptography.fernet import Fernet
            Fernet(key.encode())
            return True
        except:
            return False

    def generate_report(self):
        """Generate comprehensive test report"""
        execution_time = time.time() - self.start_time

        print("=" * 70)
        print("CAR RENTAL SYSTEM - TEST EXECUTION REPORT")
        print("=" * 70)

        # Test Results Summary
        total_files = len(self.results)
        passed_files = sum(1 for r in self.results.values() if r["status"] == "PASSED")
        failed_files = sum(1 for r in self.results.values() if r["status"] == "FAILED")

        print(f"Test Files: {total_files}")
        print(f"Passed: {passed_files}")
        print(f"Failed: {failed_files}")
        print(f"Success Rate: {(passed_files / total_files) * 100:.1f}%")
        print(f"Execution Time: {execution_time:.2f}s")

        # Detailed Results
        print("\nTest Suite Results:")
        for test_file, result in self.results.items():
            service_name = test_file.split("/")[-1].replace("test_", "").replace(".py", "")
            status_indicator = "PASS" if result["status"] == "PASSED" else "FAIL"
            print(f"  {service_name:15} {status_indicator:4} {result['details']}")

        # Azure Configuration Status
        azure_checks = self.validate_azure_configuration()
        print("\nAzure Integration Status:")
        for component, status in azure_checks.items():
            status_text = "OK" if status else "FAIL"
            print(f"  {component:15} {status_text}")

        # Final Assessment
        print("\n" + "=" * 70)
        azure_ready = sum(azure_checks.values()) >= 3
        tests_passing = passed_files == total_files

        if tests_passing and azure_ready:
            print("ASSESSMENT: PRODUCTION READY")
            print("- All test suites passing")
            print("- Azure integration validated")
            print("- System ready for deployment")
            return True
        elif tests_passing:
            print("ASSESSMENT: TESTS PASSING")
            print("- All test suites passing")
            print("- Azure configuration needs review")
            return True
        else:
            print("ASSESSMENT: REQUIRES ATTENTION")
            print("- Test failures detected")
            print("- Address issues before deployment")
            return False

    def run(self):
        """Execute complete test suite"""
        print("CAR RENTAL SYSTEM - TEST SUITE")
        print("Validating microservices and Azure integration")
        print("-" * 50)

        # Environment setup
        if not self.setup_environment():
            return False
        if not self.check_dependencies():
            return False

        # Test execution
        test_suites = [
            "tests/test_user_service.py",
            "tests/test_car_service.py",
            "tests/test_rental_service.py",
            "tests/test_common.py"
        ]

        print(f"Executing {len(test_suites)} test suites...")

        for test_file in test_suites:
            print(f"Running {test_file.split('/')[-1]}...", end=" ")
            result = self.run_test_suite(test_file)
            self.results[test_file] = result

            if result["status"] == "PASSED":
                print("PASS")
            else:
                print("FAIL")

        # Generate final report
        success = self.generate_report()
        return success


def main():
    """Main entry point"""
    runner = TestRunner()
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()