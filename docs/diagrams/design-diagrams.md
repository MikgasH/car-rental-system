# Car Rental System - Architecture & Implementation

## System Overview
Cloud-native microservices system for car rental management built with Python FastAPI and Azure services.

## 1. Implemented Microservices

### User Management Service (Port 5001)
- User registration and profile management
- PII data encryption (email, names, phone)
- RESTful API with CRUD operations
- **Endpoints:** `/health`, `/ping`, `/metrics`, `/users`

### Car Management Service (Port 5002)
- Car inventory management and search
- License plate encryption
- Availability tracking and status updates
- Azure Service Bus message consumption
- **Endpoints:** `/cars`, `/cars/available/{location}`, `/cars/status/{status}`

### Rental Management Service (Port 5003)
- Booking creation and management
- Business logic validation (dates, amounts)
- Cross-service integration (user/car validation)
- Azure Service Bus message production
- **Endpoints:** `/rentals`, rental status updates

## 2. Database Tables Diagram

### Users Table:Add commentMore actions
```sql
Users (Azure SQL Database)
├── user_id (PK, UNIQUEIDENTIFIER)
├── email (NVARCHAR(255), ENCRYPTED)
├── password_hash (NVARCHAR(255))
├── first_name (NVARCHAR(100), ENCRYPTED)
├── last_name (NVARCHAR(100), ENCRYPTED)
├── phone (NVARCHAR(20), ENCRYPTED)
├── created_at (DATETIME2)
└── updated_at (DATETIME2)
```

### Cars Table
```sql
Cars (Azure SQL Database)
├── car_id (PK, UNIQUEIDENTIFIER)
├── make (NVARCHAR(50))
├── model (NVARCHAR(50))
├── year (INT)
├── license_plate (NVARCHAR(20), ENCRYPTED)
├── status (NVARCHAR(20)) -- available/rented/maintenance
├── daily_rate (DECIMAL(10,2))
├── location (NVARCHAR(100))
├── created_at (DATETIME2)
└── updated_at (DATETIME2)
```

### Rentals Table:Add commentMore actions
```sql
Rentals (Azure SQL Database)
├── rental_id (PK, UNIQUEIDENTIFIER)
├── user_id (FK, UNIQUEIDENTIFIER)
├── car_id (FK, UNIQUEIDENTIFIER)
├── start_date (DATETIME2)
├── end_date (DATETIME2)
├── total_amount (DECIMAL(10,2))
├── status (NVARCHAR(20)) -- pending/active/completed/cancelled
├── pickup_location (NVARCHAR(255), ENCRYPTED)
├── return_location (NVARCHAR(255), ENCRYPTED)
├── created_at (DATETIME2)
└── updated_at (DATETIME2)Add commentMore actions
```

## 3. Azure Integration

### Azure SQL Database
- **Server:** car-rental-sql-server.database.windows.net
- **Databases:** user_service_db, car_service_db, rental_service_db
- **Security:** Encrypted connections, PII field encryption
- **Tables:** Users, Cars, Rentals with proper relationships

### Azure Service Bus
- **Namespace:** car-rental-servicebus.servicebus.windows.net
- **Queue:** car-status-queue
- **Messages:** rental.created, car.status.updated
- **Pattern:** Producer (Rental) → Consumer (Car)

### Azure Storage Account
- **Account:** carrentalstorage2025
- **Purpose:** Application logs and file storage
- **Integration:** Ready for log aggregation

## 4. Security Implementation

### Data Encryption
- **Algorithm:** AES-256 (Fernet)
- **PII Fields:** email, first_name, last_name, phone, license_plate, locations
- **Key Management:** Environment variable stored securely
- **Database:** Encrypted at rest, decrypted for API responses

### Authentication & Authorization
- **Current:** Basic service-to-service validation
- **Planned:** JWT tokens, role-based access control

## 5. Technical Architecture

### Technology Stack
- **Backend:** Python 3.12+ with FastAPI
- **Database:** Azure SQL Database with pyodbc
- **Messaging:** Azure Service Bus
- **Testing:** pytest with 71 comprehensive tests
- **CI/CD:** Azure DevOps Pipelines
- **Monitoring:** Built-in health/metrics endpoints

### Service Communication
```
[Load Balancer] → [API Gateway]
        │
    ┌───┼───┐
    │   │   │
[User][Car][Rental]
    │   │   │
    └───┼───┘
        │
[Azure Service Bus]
        │
[Azure SQL Database]
```

### Message Flow
1. **Rental Created** → Service Bus message sent
2. **Car Service** → Receives message, updates car status
3. **Cross-Service Calls** → User/Car validation during rental creation

## 6. Testing & Quality Assurance

### Test Coverage
- **71 total tests** across all services
- **Unit Tests:** Individual service functionality
- **Integration Tests:** Azure services connectivity
- **Business Logic Tests:** Rental rules, data validation
- **Security Tests:** Encryption/decryption verification

### Test Categories
- Service endpoints (health, ping, metrics)
- CRUD operations with validation
- Azure integration (database, service bus)
- PII encryption verification
- Cross-service communication

## 7. CI/CD Pipeline

### Pipeline Stages
1. **Build:** Install dependencies, validate structure, create artifacts
2. **Test:** Run 71 tests, validate all services
3. **Deploy:** Simulate Azure deployment, verify endpoints

### Automation
- **Trigger:** Push to main branch
- **Environment:** Ubuntu with Python 3.12
- **Artifacts:** Complete application package
- **Validation:** Health checks and service verification

## 8. Monitoring & Metrics

### Required Endpoints (All Services)
- `GET /health` - Service health status
- `GET /ping` - Connectivity check
- `GET /metrics` - Application metrics

### Collected Metrics
- **User Service:** Total users, active users
- **Car Service:** Total cars, available/rented/maintenance counts, average daily rate
- **Rental Service:** Total rentals by status, revenue metrics

## 9. Deployment Architecture

### Azure Resources
```
Azure Resource Group: car-rental-system
├── SQL Server: car-rental-sql-server
│   ├── user_service_db
│   ├── car_service_db
│   └── rental_service_db
├── Service Bus: car-rental-servicebus
│   └── Queue: car-status-queue
└── Storage Account: carrentalstorage2025
    └── Container: logs
```

### Production Readiness
- **Database:** Azure SQL with encrypted connections
- **Messaging:** Reliable message processing with error handling
- **Security:** PII encryption, secure connections
- **Monitoring:** Comprehensive health checks
- **Testing:** 100% test suite passing
- **Documentation:** Complete API documentation

## 10. Business Logic Implementation

### User Management
- User registration with encrypted PII
- Profile updates and data retrieval
- Duplicate email prevention

### Car Management
- Inventory tracking with status management
- Location-based search functionality
- License plate encryption for privacy

### Rental Management
- Date validation and business rules
- Amount calculation based on duration
- Status workflow (pending → active → completed)
- Cross-service validation for users and cars