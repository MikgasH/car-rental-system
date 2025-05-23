# Car Rental System - Design Diagrams

## 1. Functional Requirements Diagram

### Core Functions:
- **User Management**: Registration, Login, Profile management
- **Car Management**: Add cars, Update availability, Search cars
- **Rental Management**: Create booking, Manage rental status, Return car
- **Payment Processing**: Process payments, Handle refunds, Payment history
- **Notifications**: Email/SMS confirmations, Rental reminders

### User Stories:
- As a customer, I want to search available cars by location and date
- As a customer, I want to book a car and make payment
- As a customer, I want to view my rental history
- As an admin, I want to manage car inventory
- As an admin, I want to view rental statistics

## 2. Non-Functional Requirements

### Performance:
- Response time < 2 seconds for search queries
- Support 1000+ concurrent users
- 99.9% uptime availability

### Security:
- PII data encryption in database
- Message encryption between services
- JWT authentication
- HTTPS only communication

### Scalability:
- Horizontal scaling capability
- Auto-scaling based on load
- Database read replicas

### Monitoring:
- Health checks on all services (`/health`, `/ping`, `/metrics`)
- Application metrics collection
- Centralized logging

## 3. Services Communication Diagram

```
[API Gateway/Load Balancer]
            |
    ┌───────┼───────┐
    │       │       │
[Users]  [Cars]  [Rentals] ←→ [Payments]
  │       │       │              │
  └───────┼───────┘              │
          │                      │
    [Azure Service Bus] ←────────┘
          │
    [Notification Service]
          │
    [Azure Storage (Logs)]
```

### Service Responsibilities:

**User Management Service** (Port 5001):
- User registration/authentication
- Profile management
- JWT token generation
- Endpoints: `/health`, `/ping`, `/metrics`, `/users`, `/register`

**Car Management Service** (Port 5002):
- Car inventory management
- Availability tracking
- Search functionality

**Rental Management Service** (Port 5003):
- Booking creation/management
- Rental status tracking
- Integration with payments

**Payment Service** (Port 5004):
- Payment processing
- Transaction history
- Refund handling

### Message Queue Communications:
- `rental.created` → Payment Service
- `payment.completed` → Rental Service
- `rental.confirmed` → Notification Service
- `car.returned` → Car Service (update availability)

## 4. Database Tables Diagram

### Users Table:
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

### Cars Table:
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

### Rentals Table:
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
└── updated_at (DATETIME2)
```

### Payments Table:
```sql
Payments (Azure SQL Database)
├── payment_id (PK, UNIQUEIDENTIFIER)
├── rental_id (FK, UNIQUEIDENTIFIER)
├── amount (DECIMAL(10,2))
├── currency (NVARCHAR(3))
├── status (NVARCHAR(20)) -- pending/completed/failed/refunded
├── payment_method (NVARCHAR(50), ENCRYPTED)
├── transaction_id (NVARCHAR(100), ENCRYPTED)
├── created_at (DATETIME2)
└── updated_at (DATETIME2)
```

### Application_Logs Table:
```sql
Application_Logs (Azure SQL Database)
├── log_id (PK, UNIQUEIDENTIFIER)
├── service_name (NVARCHAR(50))
├── level (NVARCHAR(10)) -- INFO/WARN/ERROR
├── message (NVARCHAR(MAX), ENCRYPTED if contains PII)
├── timestamp (DATETIME2)
├── user_id (UNIQUEIDENTIFIER, nullable)
└── additional_data (NVARCHAR(MAX)) -- JSON format
```

## Technology Stack:

**Backend**: Python 3.12+ (FastAPI)
**Database**: Azure SQL Database
**Message Queue**: Azure Service Bus
**Storage**: Azure Storage Account (Blob Storage)
**Hosting**: Azure App Service (Linux)
**CI/CD**: Azure DevOps Pipelines
**Monitoring**: Built-in metrics endpoints
**Caching**: In-memory caching (Redis planned)

## Security Implementation:

**Data Encryption**:
- PII fields encrypted using AES-256
- Environment variables for encryption keys
- Database connection strings secured in Azure Key Vault

**Message Security**:
- Service Bus messages encrypted in transit
- JWT tokens for API authentication
- HTTPS enforced on all endpoints

**Authentication & Authorization**:
- JWT-based authentication
- Role-based access control (RBAC)
- Azure AD integration (planned)

## Azure Deployment Architecture:

```
[Azure Load Balancer]
         |
[App Service Plan - Linux B1]
    |    |    |    |
[User] [Car] [Rental] [Payment]
    |    |    |    |
[Azure SQL Database Server]
    |
[car_rental_db]
         |
[Azure Service Bus Namespace]
    |
[car-rental-servicebus]
         |
[Azure Storage Account]
    |
[carrentalstorage2025] → [Blob Storage for logs]
```

## Metrics and Monitoring:

### Required Endpoints (5 points):
- `GET /health` - Service health status
- `GET /ping` - Simple connectivity check  
- `GET /metrics` - Application performance metrics

### Metrics Collected:
- Request count and response times
- System resource usage (CPU, Memory)
- Business metrics (active users, rentals, etc.)
- Error rates and status codes

## Message Processing Architecture:

### Queue Structure:
```
Azure Service Bus Topics:
├── rental-events
│   ├── rental.created
│   ├── rental.updated
│   └── rental.completed
├── payment-events
│   ├── payment.requested
│   ├── payment.completed
│   └── payment.failed
└── notification-events
    ├── email.send
    └── sms.send
```

### Producer/Consumer Pattern:
- **Producers**: All services can publish events
- **Consumers**: Services subscribe to relevant topics
- **Dead Letter Queue**: Failed message handling

This architecture ensures scalability, maintainability, and meets all course requirements for the CloudTech final project.