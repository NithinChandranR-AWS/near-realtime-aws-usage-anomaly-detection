# Deployment Guide

This guide provides step-by-step instructions for deploying the Multi-Account AWS Usage Anomaly Detection System.

## Prerequisites

### AWS Account Setup
- AWS Organizations enabled
- Management account access with administrative permissions
- At least one member account in the organization

### Local Environment
- AWS CLI configured with appropriate credentials
- AWS CDK v2.110.0 or higher
- Python 3.8 or higher
- Node.js 18 or higher

### Required Permissions
The deployment requires the following AWS service permissions:
- CloudFormation (full access)
- Lambda (full access)
- OpenSearch (full access)
- CloudWatch (full access)
- SNS (full access)
- IAM (full access)
- CloudTrail (full access)
- Organizations (read access)
- Q Business (full access, optional)

## Deployment Options

### Option 1: New Organization Trail

For organizations without an existing CloudTrail:

```bash
# Set deployment mode
export CDK_CONTEXT_deployment_mode=multi-account

# Deploy all stacks
cdk deploy --all --require-approval never
```

### Option 2: Existing Organization Trail

For organizations with an existing CloudTrail:

```bash
# Set deployment mode and existing trail context
export CDK_CONTEXT_deployment_mode=multi-account
export CDK_CONTEXT_use_existing_trail=true
export CDK_CONTEXT_existing_log_group_name=your-existing-log-group-name

# Deploy without organization trail stack
cdk deploy EnhancedUsageAnomalyDetectorStack MultiAccountAnomalyStack QBusinessInsightsStack --require-approval never
```

### Option 3: Automated Deployment

Use the provided deployment script:

```bash
# Make script executable
chmod +x deploy_multi_account_enhanced.sh

# Run deployment
./deploy_multi_account_enhanced.sh
```

## Step-by-Step Deployment

### Step 1: Environment Preparation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd multi-account-anomaly-detection
   ```

2. **Create virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Bootstrap CDK**:
   ```bash
   cdk bootstrap
   ```

### Step 2: Configuration

1. **Review configuration files**:
   - `cdk.json`: CDK application configuration
   - `lambdas/CrossAccountAnomalyProcessor/config.py`: Anomaly detection thresholds

2. **Set deployment context** (optional):
   ```bash
   # For existing trail deployment
   cdk deploy --context use-existing-trail=true --context existing-log-group-name=YOUR_LOG_GROUP_NAME
   ```

### Step 3: Stack Deployment

Deploy stacks in the following order:

1. **Organization Trail Stack** (if creating new trail):
   ```bash
   cdk deploy OrganizationTrailStack
   ```

2. **Enhanced Usage Anomaly Detector Stack**:
   ```bash
   cdk deploy EnhancedUsageAnomalyDetectorStack
   ```

3. **Multi-Account Anomaly Stack**:
   ```bash
   cdk deploy MultiAccountAnomalyStack
   ```

4. **Q Business Insights Stack** (optional):
   ```bash
   cdk deploy QBusinessInsightsStack
   ```

### Step 4: Post-Deployment Configuration

1. **Subscribe to SNS alerts**:
   ```bash
   aws sns subscribe \
     --topic-arn <SystemAlertsTopicArn> \
     --protocol email \
     --notification-endpoint your-email@example.com
   ```

2. **Configure Q Business users** (if deployed):
   - Access AWS Identity Center
   - Add users to the "QBusinessAdmins" group
   - Configure application assignments

3. **Verify OpenSearch access**:
   - Access OpenSearch Dashboards
   - Import provided dashboard configurations
   - Test anomaly detection queries

### Step 5: Validation

Run the validation script to ensure proper deployment:

```bash
python validate_enhanced_deployment.py
```

## Configuration Options

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_DEFAULT_REGION` | AWS region for deployment | `us-east-1` |
| `CDK_CONTEXT_deployment_mode` | Deployment mode | `multi-account` |
| `CDK_CONTEXT_use_existing_trail` | Use existing trail | `true` |
| `CDK_CONTEXT_existing_log_group_name` | Existing log group | `aws-cloudtrail-logs-123456789012-abcd1234` |

### Account Tagging

Tag your AWS accounts for proper categorization:

```bash
aws organizations tag-resource \
  --resource-id 123456789012 \
  --tags Key=AccountType,Value=production Key=Environment,Value=prod
```

### Threshold Configuration

Customize anomaly detection thresholds in `lambdas/CrossAccountAnomalyProcessor/config.py`:

```python
THRESHOLDS = {
    'production': {
        'ec2': 10,      # EC2 instance launches per hour
        'lambda': 1000, # Lambda invocations per hour
        'ebs': 20       # EBS volume creations per hour
    },
    'staging': {
        'ec2': 5,
        'lambda': 500,
        'ebs': 10
    },
    'development': {
        'ec2': 2,
        'lambda': 100,
        'ebs': 5
    }
}
```

## Monitoring Setup

### CloudWatch Dashboard

The deployment creates a comprehensive dashboard with:
- Lambda function performance metrics
- OpenSearch cluster health
- Anomaly detection accuracy
- System health scores

### Custom Metrics

Monitor these key metrics:
- `MultiAccountAnomalyDetection/OverallHealthScore`
- `MultiAccountAnomalyDetection/ProcessingSuccessRate`
- `MultiAccountAnomalyDetection/AnomalyDetectionAccuracy`

### Alerting

Configure alerts for:
- High error rates in Lambda functions
- OpenSearch cluster issues
- Low processing success rates
- System health degradation

## Troubleshooting

### Common Issues

1. **CDK Bootstrap Issues**:
   ```bash
   cdk bootstrap --force
   ```

2. **Permission Errors**:
   - Verify IAM permissions
   - Check organization management account access
   - Ensure CDK execution role has required permissions

3. **Stack Dependencies**:
   - Deploy stacks in the correct order
   - Verify cross-stack references
   - Check CloudFormation stack outputs

4. **Q Business Integration**:
   - Verify CDK version >= 2.110.0
   - Check Identity Center configuration
   - Ensure Q Business service availability in region

### Validation Commands

```bash
# Check stack status
aws cloudformation describe-stacks --stack-name MultiAccountAnomalyStack

# Verify Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `MultiAccount`)]'

# Check OpenSearch domain
aws opensearch describe-domain --domain-name <domain-name>

# Test Q Business integration
aws qbusiness list-applications
```

## Cleanup

To remove all deployed resources:

```bash
# Destroy all stacks
cdk destroy --all

# Or use the cleanup script
./deploy_multi_account_enhanced.sh --cleanup
```

**Note**: Some resources like S3 buckets may need manual deletion if they contain data.

## Next Steps

After successful deployment:

1. **Configure user access** to OpenSearch and Q Business
2. **Set up monitoring dashboards** and alerts
3. **Test anomaly detection** with sample events
4. **Train users** on natural language querying
5. **Establish operational procedures** for anomaly response

For ongoing maintenance, see the [troubleshooting guide](troubleshooting.md).