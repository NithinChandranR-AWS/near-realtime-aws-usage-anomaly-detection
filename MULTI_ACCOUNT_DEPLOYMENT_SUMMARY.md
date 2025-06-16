# Multi-Account Deployment Summary

## Overview
The multi-account deployment is configured to support all the same AWS services as the single-account deployment:

### Supported Services and Events

1. **EC2 (RunInstances)**
   - Captured via: Management Events in CloudTrail
   - Anomaly Detector: `multi-account-ec2-run-instances`
   - Category Fields: `recipientAccountId`, `awsRegion`

2. **Lambda (Invoke)**
   - Captured via: Data Events in CloudTrail
   - Anomaly Detector: `multi-account-lambda-invoke`
   - Category Fields: `recipientAccountId`, `requestParameters.functionName.keyword`

3. **EBS (CreateVolume)**
   - Captured via: Management Events in CloudTrail
   - Anomaly Detector: `multi-account-ebs-create-volume`
   - Category Fields: `recipientAccountId`, `awsRegion`

## CloudTrail Configuration

### Organization Trail Stack (`organization_trail_stack.py`)
- **Management Events**: ✅ Enabled (`include_management_events=True`)
  - Captures EC2 RunInstances and EBS CreateVolume events
- **Data Events**: ✅ Configured for Lambda functions
  - Type: `AWS::Lambda::Function`
  - Values: `arn:aws:lambda:*:*:function/*`

### Key Points
- EC2 and EBS events are **management events**, not data events
- CloudTrail does NOT support `AWS::EC2::Instance` as a data resource type
- All EC2 API calls (including RunInstances) are automatically captured when management events are enabled

## Multi-Account Anomaly Detectors

### Enhanced Anomaly Detector Stack (`enhanced_anomaly_detector_stack_test.py`)
Configured detectors:
```python
"detectors": [
    {
        "name": "multi-account-ec2-run-instances",
        "category_fields": ["recipientAccountId", "awsRegion"],
    },
    {
        "name": "multi-account-lambda-invoke",
        "category_fields": [
            "recipientAccountId",
            "requestParameters.functionName.keyword",
        ],
    },
    {
        "name": "multi-account-ebs-create-volume",
        "category_fields": ["recipientAccountId", "awsRegion"],
    },
]
```

## Deployment Command

```bash
cdk deploy --app "python3 app_enhanced_test.py" \
  --context deployment-mode=multi-account \
  --parameters EnhancedUsageAnomalyDetectorStack:opensearchalertemail=rajashan@amazon.com \
  --all \
  --require-approval never
```

## Stack Dependencies

1. **OrganizationTrailStack** - Creates organization-wide CloudTrail
2. **EnhancedUsageAnomalyDetectorStack** - Base OpenSearch domain and single-account detectors
3. **MultiAccountAnomalyStack** - Multi-account log processing and anomaly detectors
4. **QBusinessInsightsStack** (optional) - Natural language insights for anomalies

## Verification Steps

To verify the deployment:

1. Check CloudFormation stacks:
   ```bash
   aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE
   ```

2. Verify CloudTrail configuration:
   ```bash
   aws cloudtrail describe-trails --trail-name-list org-trail-OrganizationTrailStack
   ```

3. Check OpenSearch anomaly detectors:
   - Access OpenSearch Dashboards
   - Navigate to Anomaly Detection plugin
   - Verify all three detectors are created

## Feature Parity with Single-Account

✅ **EC2 RunInstances** - Full support via management events
✅ **Lambda Invoke** - Full support via data events
✅ **EBS CreateVolume** - Full support via management events

All features from the single-account deployment are available in the multi-account deployment with enhanced capabilities for cross-account visibility.
