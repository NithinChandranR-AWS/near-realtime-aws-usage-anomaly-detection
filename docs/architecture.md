# Architecture Overview

## Multi-Account AWS Usage Anomaly Detection System

### High-Level Architecture

```mermaid
graph TB
    subgraph "AWS Organization"
        subgraph "Account 1"
            A1[CloudTrail Events]
        end
        subgraph "Account 2"
            A2[CloudTrail Events]
        end
        subgraph "Account N"
            AN[CloudTrail Events]
        end
    end
    
    subgraph "Management Account"
        CT[Organization CloudTrail]
        CWL[CloudWatch Logs]
        
        subgraph "Processing Layer"
            LAM[Multi-Account Logs Lambda]
            CONFIG[Config Lambda]
        end
        
        subgraph "Storage & Analytics"
            OS[OpenSearch Domain]
            AD[Anomaly Detectors]
        end
        
        subgraph "Insights Layer"
            QC[Q Business Connector]
            QB[Q Business Application]
            IC[Identity Center]
        end
        
        subgraph "Monitoring"
            CWD[CloudWatch Dashboard]
            SNS[SNS Alerts]
            SHM[System Health Monitor]
        end
    end
    
    subgraph "User Access"
        U1[Security Team]
        U2[Operations Team]
        U3[Management]
    end
    
    A1 --> CT
    A2 --> CT
    AN --> CT
    CT --> CWL
    CWL --> LAM
    LAM --> OS
    CONFIG --> OS
    OS --> AD
    AD --> SNS
    OS --> QC
    QC --> QB
    QB --> IC
    
    U1 --> OS
    U1 --> QB
    U1 --> CWD
    U2 --> OS
    U2 --> CWD
    U3 --> QB
    
    style CT fill:#ff9999
    style OS fill:#99ccff
    style QB fill:#99ff99
    style SNS fill:#ffcc99
```

### Component Details

#### Data Collection Layer
- **Organization CloudTrail**: Captures management and data events from all accounts
- **CloudWatch Logs**: Centralized log aggregation point
- **Multi-Account Logs Lambda**: Processes and enriches events with account metadata

#### Analytics Layer
- **OpenSearch Domain**: Stores and indexes log data for analysis
- **Anomaly Detectors**: High-cardinality detectors categorized by account and region
- **Config Lambda**: Automatically configures detectors for new accounts

#### Insights Layer
- **Q Business Application**: Natural language interface for querying anomalies
- **Q Business Connector**: Synchronizes anomaly data for natural language processing
- **Identity Center**: Provides secure authentication and authorization

#### Monitoring Layer
- **CloudWatch Dashboard**: Real-time system health and performance metrics
- **SNS Topics**: Multi-channel alerting for anomalies and system health
- **System Health Monitor**: Automated health checks and custom metrics

### Data Flow

```mermaid
sequenceDiagram
    participant Accounts as AWS Accounts
    participant Trail as Organization Trail
    participant Logs as CloudWatch Logs
    participant Lambda as Processing Lambda
    participant OS as OpenSearch
    participant AD as Anomaly Detectors
    participant QB as Q Business
    participant Users as End Users
    
    Accounts->>Trail: API Events
    Trail->>Logs: Structured Logs
    Logs->>Lambda: Log Stream
    Lambda->>Lambda: Enrich with Account Metadata
    Lambda->>OS: Indexed Events
    OS->>AD: Trigger Analysis
    AD->>AD: Detect Anomalies
    AD->>QB: Sync Anomaly Data
    Users->>QB: Natural Language Query
    QB->>Users: Contextual Insights
    AD->>Users: Alert Notifications
```

### Security Architecture

```mermaid
graph LR
    subgraph "Identity & Access"
        IC[Identity Center]
        IAM[IAM Roles]
        RBAC[Role-Based Access]
    end
    
    subgraph "Data Protection"
        KMS[KMS Encryption]
        TLS[TLS in Transit]
        VPC[VPC Isolation]
    end
    
    subgraph "Monitoring"
        CT[CloudTrail Audit]
        CW[CloudWatch Logs]
        AL[Access Logging]
    end
    
    IC --> RBAC
    IAM --> RBAC
    RBAC --> KMS
    RBAC --> TLS
    RBAC --> VPC
    
    CT --> AL
    CW --> AL
    
    style IC fill:#ff9999
    style KMS fill:#99ccff
    style CT fill:#99ff99
```

### Deployment Architecture

```mermaid
graph TD
    subgraph "CDK Stacks"
        OTS[OrganizationTrailStack]
        EAS[EnhancedAnomalyDetectorStack]
        MAS[MultiAccountAnomalyStack]
        QBS[QBusinessStack]
    end
    
    subgraph "Dependencies"
        OTS --> MAS
        EAS --> MAS
        MAS --> QBS
    end
    
    subgraph "Resources"
        OTS --> CT[CloudTrail + S3 + KMS]
        EAS --> OS[OpenSearch + Cognito]
        MAS --> LAM[Lambda Functions + SNS]
        QBS --> QB[Q Business + Identity Center]
    end
    
    style OTS fill:#ff9999
    style EAS fill:#99ccff
    style MAS fill:#99ff99
    style QBS fill:#ffcc99
```