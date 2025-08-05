
# Enhanced Multi-Account AWS Usage Anomaly Detection - Architecture Diagram

## System Architecture

```mermaid
graph TB
    subgraph "AWS Organization"
        subgraph "Management Account"
            OrgTrail[Organization CloudTrail<br/>Multi-Region Trail]
            TrailBucket[S3 Bucket<br/>Encrypted CloudTrail Logs<br/>Lifecycle Policies]
            TrailKMS[KMS Key<br/>Trail Encryption<br/>Key Rotation Enabled]
            CWLogs[CloudWatch Logs<br/>Organization Trail<br/>Real-time Streaming]
        end
        
        subgraph "Member Accounts"
            MA1[Production Account<br/>Critical Workloads]
            MA2[Staging Account<br/>Pre-production Testing] 
            MA3[Development Account<br/>Development & Testing]
            MA4[Sandbox Account<br/>Experimentation]
        end
    end
    
    subgraph "Enhanced Anomaly Detection System"
        subgraph "Data Processing Layer"
            LogsLambda[Multi-Account Logs Lambda<br/>Node.js 18.x<br/>Account Enrichment<br/>Retry Logic & Caching]
            AccountCache[DynamoDB Table<br/>Account Metadata Cache<br/>TTL Enabled<br/>GSI for Queries]
            OrgAPI[AWS Organizations API<br/>Account Metadata<br/>Organizational Units<br/>Account Tags]
        end
        
        subgraph "Storage & Analytics Layer"
            OpenSearch[Amazon OpenSearch<br/>Multi-AZ Cluster<br/>3 Data Nodes<br/>Encryption at Rest]
            OSIndices[OpenSearch Indices<br/>cwl-multiaccounts*<br/>Account-Aware Mapping<br/>Optimized for Search]
            AnomalyDetectors[ML Anomaly Detectors<br/>Account-Based Categories<br/>EC2, Lambda, EBS<br/>Auto-scaling Thresholds]
        end
        
        subgraph "AI & Natural Language Layer"
            QBusiness[Amazon Q Business<br/>Application & Index<br/>Natural Language Interface<br/>Conversational AI]
            QConnector[Q Business Connector<br/>Python 3.9<br/>Data Synchronization<br/>Document Transformation]
            InsightsLambda[NL Insights Generator<br/>Cost Impact Analysis<br/>Root Cause Analysis<br/>Intelligent Recommendations]
        end
        
        subgraph "Monitoring & Alerting Layer"
            CWDashboard[CloudWatch Dashboards<br/>Real-time Metrics<br/>System Health<br/>Anomaly Visualization]
            SNSTopic[SNS Topics<br/>Multi-channel Alerts<br/>Email, Slack, Teams<br/>Enhanced Notifications]
            HealthMonitor[System Health Monitor<br/>Proactive Monitoring<br/>Custom Metrics<br/>Automated Recovery]
        end
        
        subgraph "Security & Access Control"
            Cognito[Amazon Cognito<br/>User Pool & Identity Pool<br/>MFA Support<br/>Password Policies]
            IdentityCenter[AWS Identity Center<br/>SSO Integration<br/>Q Business Authentication<br/>SAML/OIDC Support]
            IAMRoles[IAM Roles<br/>Cross-Account Access<br/>Least Privilege<br/>Temporary Credentials]
        end
    end
    
    subgraph "User Interfaces"
        OSKibana[OpenSearch Dashboards<br/>Data Visualization<br/>Custom Dashboards<br/>Anomaly Investigation]
        QChat[Q Business Chat Interface<br/>Natural Language Queries<br/>Conversational Analytics<br/>Mobile Responsive]
        CWConsole[CloudWatch Console<br/>Metrics & Alarms<br/>Log Analysis<br/>Performance Monitoring]
    end
    
    %% Data Flow Connections
    MA1 --> OrgTrail
    MA2 --> OrgTrail
    MA3 --> OrgTrail
    MA4 --> OrgTrail
    
    OrgTrail --> TrailBucket
    OrgTrail --> CWLogs
    TrailKMS --> TrailBucket
    
    CWLogs --> LogsLambda
    LogsLambda --> AccountCache
    LogsLambda --> OrgAPI
    LogsLambda --> OpenSearch
    
    OpenSearch --> OSIndices
    OSIndices --> AnomalyDetectors
    
    AnomalyDetectors --> SNSTopic
    OpenSearch --> QConnector
    QConnector --> QBusiness
    
    QBusiness --> InsightsLambda
    InsightsLambda --> SNSTopic
    
    HealthMonitor --> CWDashboard
    OpenSearch --> CWDashboard
    
    %% User Access Flows
    Cognito --> OSKibana
    IdentityCenter --> QChat
    IAMRoles --> CWConsole
    
    %% User Connections
    Users[End Users<br/>Security Teams<br/>DevOps Engineers<br/>Business Stakeholders] --> OSKibana
    Users --> QChat
    Users --> CWConsole
    
    %% Styling
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef storage fill:#3F48CC,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef compute fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef ai fill:#01A88D,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef security fill:#DD344C,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef monitoring fill:#8C4FFF,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef ui fill:#146EB4,stroke:#232F3E,stroke-width:2px,color:#fff
    
    class OrgTrail,MA1,MA2,MA3,MA4,OrgAPI aws
    class TrailBucket,AccountCache,OpenSearch,OSIndices storage
    class LogsLambda,QConnector,InsightsLambda,HealthMonitor compute
    class QBusiness,QChat ai
    class TrailKMS,Cognito,IdentityCenter,IAMRoles security
    class CWDashboard,SNSTopic,HealthMonitor monitoring
    class OSKibana,CWConsole,Users ui
```

## Data Flow Description

### 1. Event Collection (Real-time)
- CloudTrail events from all organization member accounts flow to the centralized organization trail
- Events are encrypted using KMS and stored in S3 with intelligent lifecycle policies
- Real-time streaming to CloudWatch Logs enables immediate processing

### 2. Intelligent Processing (Sub-5 minute latency)
- Multi-Account Logs Lambda processes events with account enrichment
- Account metadata is cached in DynamoDB with TTL for performance
- Organizations API provides organizational context and account classification

### 3. Advanced Analytics (ML-powered)
- OpenSearch cluster provides scalable storage and search capabilities
- ML anomaly detectors analyze patterns with account-aware categorization
- Multi-dimensional analysis across accounts, regions, and services

### 4. AI-Powered Insights (Natural Language)
- Amazon Q Business enables conversational analytics
- Natural language queries provide intuitive access to complex data
- Intelligent insights include cost impact and root cause analysis

### 5. Proactive Monitoring (Automated)
- Real-time dashboards provide comprehensive system visibility
- Multi-channel alerting with intelligent context and recommendations
- Automated health monitoring with self-healing capabilities

## Key Features

### Enterprise Scale
- **Multi-Account Support**: Centralized monitoring across unlimited AWS accounts
- **High Availability**: Multi-AZ deployment with automatic failover
- **Auto Scaling**: Automatic scaling based on event volume and query load

### Advanced Security
- **Encryption Everywhere**: End-to-end encryption in transit and at rest
- **Zero Trust Architecture**: Least privilege access with temporary credentials
- **Compliance Ready**: Audit trails and compliance reporting built-in

### AI-Enhanced Analytics
- **Natural Language Queries**: "Show me EC2 anomalies from production accounts"
- **Intelligent Insights**: Automated root cause analysis and recommendations
- **Cost Intelligence**: Automatic cost impact analysis for detected anomalies

### Operational Excellence
- **Proactive Monitoring**: Health checks and automated recovery
- **Performance Optimized**: Sub-5 minute processing latency
- **Cost Optimized**: Intelligent data lifecycle and resource management
```
