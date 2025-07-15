# Enhanced Multi-Account Q Business Deployment Guide

## Overview

This guide covers the deployment and configuration of the enhanced AWS usage anomaly detection system with multi-account support and Amazon Q for Business integration.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           AWS Organization                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Management Account                    │  Member Accounts                       │
│  ┌─────────────────────────────────┐   │  ┌─────────────────────────────────┐   │
│  │ Organization CloudTrail         │   │  │ Account A                       │   │
│  │ ├─ Management Events            │◄──┤  │ ├─ EC2 RunInstances             │   │
│  │ ├─ Lambda Data Events           │   │  │ ├─ EBS CreateVolume             │   │
│  │ └─ CloudWatch Logs              │   │  │ └─ Lambda Invoke                │   │
│  └─────────────────────────────────┘   │  └─────────────────────────────────┘   │
│                │                       │                                        │
│                ▼                       │  ┌─────────────────────────────────┐   │
│  ┌─────────────────────────────────┐   │  │ Account B                       │   │
│  │ Enhanced Log Processing         │   │  │ ├─ EC2 RunInstances             │   │
│  │ ├─ Account Enrichment           │   │  │ ├─ EBS CreateVolume             │   │
│  │ ├─ Organization Context         │   │  │ └─ Lambda Invoke                │   │
│  │ └─ Multi-Account Indexing       │   │  └─────────────────────────────────┘   │
│  └─────────────────────────────────┘   │                                        │
│                │                       │                                        │
│                ▼                       │                                        │
│  ┌─────────────────────────────────┐   │                                        │
│  │ OpenSearch Domain               │   │                                        │
│  │ ├─ Multi-Account Indices        │   │                                        │
│  │ ├─ High-Cardinality Detectors   │   │                                        │
│  │ ├─ Cross-Account Dashboards     │   │                                        │
│  │ └─ Alerting & Monitoring        │   │                                        │
│  └─────────────────────────────────┘   │                                        │
│                │                       │                                        │
│                ▼                       │                                        │
│  ┌─────────────────────────────────┐   │                                        │
│  │ Amazon Q for Business           │   │                                        │
│  │ ├─ Natural Language Interface   │   │                                        │
│  │ ├─ Anomaly Insights             │   │                                        │
│  │ ├─ Cost Analysis                │   │                                        │
│  │ └─ Security Recommendations     │   │                                        │
│  └─────────────────────────────────┘   │                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Environment Requirements
- **Python**: 3.8+ (3.7 works but shows warnings)
- **Node.js**: 18+ (17 works but shows warnings)
- **AWS CDK**: 2.110.0+ (for Q Business support)
- **AWS CLI**: Configured with appropriate permissions

### AWS Account Requirements
- **Organization Management Account**: Required for organization-wide CloudTrail
- **Admin Permissions**: Full access to deploy all resources
- **Service Quotas**: Ensure sufficient limits for OpenSearch, Lambda, etc.

### Supported Regions
The solution supports all regions where the following services are available:
- Amazon OpenSearch Service
- AWS CloudTrail
- Amazon Q for Business
- AWS Lambda
- Amazon Cognito

## Quick Start Deployment

### 1. Clone and Setup
```bash
git clone <repository-url>
cd near-realtime-aws-usage-anomaly-detection
pip3 install -r requirements.txt
```

### 2. Deploy with Enhanced Script
```bash
./deploy_multi_account_enhanced.sh -e your-email@company.com -r us-east-1
```

### 3. Manual Deployment (Alternative)
```bash
cdk deploy --app "python3 app_enhanced_test.py" \
  --context deployment-mode=multi-account \
  --context opensearch-version=OPENSEARCH_2_9 \
  --context enable-lambda-trail=true \
  --parameters EnhancedUsageAnomalyDetectorStack:opensearchalertemail=your-email@company.com \
  --all \
  --require-approval never
```

## Deployment Options

### Context Variables
- `deployment-mode`: `single-account` or `multi-account`
- `opensearch-version`: `OPENSEARCH_1_3`, `OPENSEARCH_2_3`, `OPENSEARCH_2_5`, `OPENSEARCH_2_7`, `OPENSEARCH_2_9`
- `enable-lambda-trail`: `true` or `false`

### Parameters
- `opensearchalertemail`: Email address for anomaly alerts

## Stack Components

### 1. OrganizationTrailStack
**Purpose**: Creates organization-wide CloudTrail for centralized logging

**Resources Created**:
- CloudTrail with organization scope
- S3 bucket for trail storage
- CloudWatch Logs group
- KMS key for encryption
- IAM roles and policies

**Key Features**:
- Management events from all accounts
- Lambda data events (if enabled)
- Multi-region trail
- Log file validation

### 2. EnhancedUsageAnomalyDetectorStack (Base)
**Purpose**: Creates OpenSearch domain and basic anomaly detection

**Resources Created**:
- OpenSearch domain with Cognito authentication
- Basic anomaly detectors
- SNS topics for alerts
- Lambda functions for log processing

### 3. MultiAccountAnomalyStack
**Purpose**: Enhances anomaly detection for multi-account scenarios

**Resources Created**:
- Multi-account log processing Lambda
- Cross-account anomaly detectors
- Enhanced dashboards
- Q Business connector Lambda

**Key Features**:
- Account metadata enrichment
- High-cardinality anomaly detection
- Cross-account correlation
- Organization context

### 4. QBusinessInsightsStack
**Purpose**: Provides natural language insights for anomalies

**Resources Created**:
- Q Business application
- Q Business index
- Identity Center integration
- KMS key and S3 bucket
- Sync Lambda functions

**Key Features**:
- Natural language querying
- Cost impact analysis
- Security recommendations
- Automated insights generation

## Multi-Account Anomaly Detectors

### EC2 RunInstances Detector
```json
{
  "name": "multi-account-ec2-run-instances",
  "category_fields": ["recipientAccountId", "awsRegion"],
  "filter": "eventName.keyword: RunInstances",
  "feature": "instance_count"
}
```

### Lambda Invoke Detector
```json
{
  "name": "multi-account-lambda-invoke", 
  "category_fields": ["recipientAccountId", "requestParameters.functionName.keyword"],
  "filter": "eventName.keyword: Invoke",
  "feature": "invocation_count"
}
```

### EBS CreateVolume Detector
```json
{
  "name": "multi-account-ebs-create-volume",
  "category_fields": ["recipientAccountId", "awsRegion"],
  "filter": "eventName.keyword: CreateVolume",
  "feature": "volume_count"
}
```

## Post-Deployment Configuration

### 1. Confirm SNS Subscriptions
1. Check your email for SNS subscription confirmations
2. Click "Confirm subscription" in each email
3. Verify subscriptions in AWS Console

### 2. Create OpenSearch Users
1. Navigate to the Cognito User Pool (URL provided in outputs)
2. Create users for OpenSearch access
3. Add users to `opensearch-admin` group for full access

### 3. Configure Identity Center for Q Business
1. Access AWS Identity Center console
2. Create users and groups for Q Business access
3. Assign appropriate permissions

### 4. Verify Anomaly Detectors
1. Access OpenSearch Dashboards
2. Navigate to Anomaly Detection plugin
3. Verify all three detectors are running
4. Check detector health and status

## Monitoring and Troubleshooting

### Common Issues and Solutions

#### 1. CDK Version Issues
**Problem**: Q Business resources fail to create
**Solution**: 
```bash
pip3 install --upgrade 'aws-cdk-lib>=2.110.0'
```

#### 2. Python/Node Version Warnings
**Problem**: EOL version warnings
**Solution**: Upgrade to supported versions or ignore warnings (functionality still works)

#### 3. Organization Trail Permissions
**Problem**: Trail creation fails
**Solution**: Ensure deployment from organization management account

#### 4. OpenSearch Domain Access
**Problem**: Cannot access OpenSearch dashboards
**Solution**: 
- Check Cognito user creation
- Verify IAM role mappings
- Ensure proper security group configuration

#### 5. Q Business Integration Issues
**Problem**: Q Business resources fail to deploy
**Solution**:
- Verify Identity Center is available in region
- Check Q Business service availability
- Ensure proper IAM permissions

### Verification Commands

```bash
# Check stack status
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE

# Verify CloudTrail
aws cloudtrail describe-trails --trail-name-list org-trail-OrganizationTrailStack

# Check OpenSearch domain
aws opensearch describe-domain --domain-name usage-anomaly-detector-os

# Verify Q Business application
aws qbusiness list-applications
```

### Log Locations

- **CloudTrail Logs**: CloudWatch Logs group `/aws/cloudtrail/organization/`
- **Lambda Logs**: CloudWatch Logs groups `/aws/lambda/`
- **OpenSearch Logs**: OpenSearch domain logs
- **CDK Deployment Logs**: Local terminal output

## Cost Optimization

### Expected Costs (Monthly Estimates)
- **OpenSearch Domain**: $200-500 (depending on instance types)
- **CloudTrail**: $2-10 (depending on event volume)
- **Lambda Functions**: $5-20 (depending on invocations)
- **Q Business**: $20-100 (depending on usage)
- **Storage (S3/EBS)**: $10-50 (depending on retention)

### Cost Reduction Tips
1. Use smaller OpenSearch instance types for testing
2. Implement lifecycle policies for log retention
3. Use reserved instances for predictable workloads
4. Monitor and optimize Lambda memory allocation
5. Set up billing alerts and budgets

## Security Considerations

### Data Protection
- All data encrypted in transit and at rest
- KMS keys for encryption management
- VPC deployment option available
- Fine-grained access control

### Access Control
- IAM roles with least privilege
- Cognito authentication for OpenSearch
- Identity Center integration for Q Business
- Cross-account trust relationships

### Compliance
- CloudTrail log file validation
- Audit trails for all actions
- Compliance dashboard available
- Regular security assessments

## Advanced Configuration

### Custom Anomaly Thresholds
Modify detector configurations in `lambdas/CrossAccountAnomalyProcessor/config.py`:

```python
# Custom thresholds per account type
THRESHOLDS = {
    'production': {'ec2': 10, 'lambda': 1000, 'ebs': 20},
    'staging': {'ec2': 5, 'lambda': 500, 'ebs': 10},
    'development': {'ec2': 2, 'lambda': 100, 'ebs': 5}
}
```

### Additional Event Types
Add new event types by modifying the detector configurations:

```python
{
    "name": "multi-account-s3-operations",
    "category_fields": ["recipientAccountId", "awsRegion"],
    "filter": "eventName.keyword: (CreateBucket OR DeleteBucket)"
}
```

### Custom Dashboards
Create additional OpenSearch dashboards for specific use cases:
- Cost analysis dashboards
- Security-focused views
- Compliance reporting
- Executive summaries

## Support and Maintenance

### Regular Maintenance Tasks
1. **Weekly**: Review anomaly alerts and false positives
2. **Monthly**: Update detector thresholds based on patterns
3. **Quarterly**: Review and optimize costs
4. **Annually**: Update to latest CDK and service versions

### Backup and Recovery
- CloudFormation templates stored in version control
- OpenSearch snapshots configured
- S3 cross-region replication for trail logs
- Disaster recovery procedures documented

### Updates and Upgrades
1. Test updates in non-production environment
2. Use CDK diff to review changes
3. Deploy during maintenance windows
4. Monitor post-deployment metrics

## Getting Help

### Documentation Resources
- [AWS OpenSearch Service Documentation](https://docs.aws.amazon.com/opensearch-service/)
- [Amazon Q for Business Documentation](https://docs.aws.amazon.com/amazonq/)
- [AWS CloudTrail Documentation](https://docs.aws.amazon.com/cloudtrail/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)

### Community Support
- AWS re:Post forums
- GitHub issues and discussions
- AWS user groups and meetups
- Stack Overflow with AWS tags

### Professional Support
- AWS Support plans
- AWS Professional Services
- AWS Partner Network consultants
- Third-party security specialists