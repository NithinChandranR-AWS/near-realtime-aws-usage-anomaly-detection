# Enhanced Multi-Account AWS Usage Anomaly Detection - Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Enhanced Multi-Account AWS Usage Anomaly Detection System with troubleshooting for common issues.

## Prerequisites

### 1. AWS Account Requirements

- **Management Account Access**: For multi-account deployment, you must deploy from the AWS Organizations management account
- **AWS Organizations**: Must be enabled with all features
- **Sufficient Permissions**: IAM permissions for CloudTrail, S3, OpenSearch, Lambda, and Organizations

### 2. Development Environment

- **AWS CLI v2**: Latest version recommended
- **AWS CDK**: Version 2.110.0 or higher
- **Node.js**: Version 18.x or higher
- **Python**: Version 3.8 or higher
- **Git**: For cloning the repository

### 3. Pre-Deployment Validation

Run the validation script to check prerequisites:

```bash
python validate_deployment_prerequisites.py
```

This script will verify:
- AWS credentials and permissions
- Organization management account access
- Required service availability in your region
- CDK bootstrap status

## Deployment Modes

### Mode 1: Single Account (Basic)
- Anomaly detection for a single AWS account
- Standard CloudTrail and OpenSearch
- Suitable for testing or small organizations

### Mode 2: Multi-Account (Enterprise)
- Organization-wide anomaly detection
- Cross-account event processing
- Account metadata enrichment

### Mode 3: Multi-Account with Q Business (AI-Enhanced)
- Full enterprise deployment
- Natural language querying
- AI-powered insights and recommendations

## Step-by-Step Deployment

### Step 1: Environment Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/NithinChandranR-AWS/near-realtime-aws-usage-anomaly-detection.git
   cd near-realtime-aws-usage-anomaly-detection
   ```

2. **Set up Python Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Verify AWS Credentials**
   ```bash
   aws sts get-caller-identity
   ```

4. **Bootstrap CDK (if not already done)**
   ```bash
   cdk bootstrap
   ```

### Step 2: Pre-Deployment Validation

```bash
python validate_deployment_prerequisites.py
```

**Expected Output:**
```
🎉 All prerequisite validations passed!
✅ Ready for deployment
```

If validation fails, resolve the issues before proceeding.

### Step 3: Choose and Deploy

#### Option A: Single Account Deployment
```bash
cdk deploy --context deployment-mode=single-account \
           --context enable-lambda-trail=false \
           --context opensearch-version=OPENSEARCH_2_9
```

#### Option B: Multi-Account Deployment
```bash
cdk deploy --context deployment-mode=multi-account \
           --context enable-lambda-trail=false \
           --context opensearch-version=OPENSEARCH_2_9
```

#### Option C: Multi-Account with Q Business
```bash
cdk deploy --context deployment-mode=multi-account-with-qbusiness \
           --context enable-lambda-trail=false \
           --context opensearch-version=OPENSEARCH_2_9
```

### Step 4: Post-Deployment Validation

```bash
python validate_enhanced_deployment.py
```

## Troubleshooting Common Issues

### Issue 1: S3 Bucket Policy Error

**Error Message:**
```
Incorrect S3 bucket policy is detected for bucket: org-trail-xxx
```

**Root Cause:** Missing or incorrect S3 bucket permissions for organization trails.

**Solution:**
1. The updated OrganizationTrailStack includes comprehensive bucket policies
2. If you encounter this error, delete the failed stack and redeploy:
   ```bash
   cdk destroy OrganizationTrailStack
   cdk deploy --context deployment-mode=multi-account
   ```

### Issue 2: Organization Trail Creation Failed

**Error Message:**
```
Cannot create trail. Organization trail already exists
```

**Root Cause:** An organization trail already exists in your account.

**Solutions:**

**Option A: Use Existing Trail**
1. Identify the existing trail:
   ```bash
   aws cloudtrail describe-trails --query 'trailList[?IsOrganizationTrail==`true`]'
   ```
2. Deploy without creating a new trail:
   ```bash
   cdk deploy --context deployment-mode=single-account
   ```

**Option B: Delete Existing Trail (if safe)**
1. Stop logging on the existing trail:
   ```bash
   aws cloudtrail stop-logging --name <existing-trail-name>
   ```
2. Delete the existing trail:
   ```bash
   aws cloudtrail delete-trail --name <existing-trail-name>
   ```
3. Redeploy:
   ```bash
   cdk deploy --context deployment-mode=multi-account
   ```

### Issue 3: OpenSearch Domain Creation Failed

**Error Message:**
```
Domain creation failed: Service limit exceeded
```

**Root Cause:** AWS service limits for OpenSearch domains.

**Solution:**
1. Check current OpenSearch domains:
   ```bash
   aws es list-domain-names
   ```
2. Delete unused domains or request limit increase
3. Use existing domain context:
   ```bash
   cdk deploy --context opensearch-domain-endpoint=<existing-domain-endpoint>
   ```

### Issue 4: Lambda Function Timeout

**Error Message:**
```
Lambda function timeout during deployment
```

**Root Cause:** Lambda functions timing out during custom resource operations.

**Solution:**
1. Check CloudWatch Logs for the specific Lambda function
2. Increase timeout in the stack configuration
3. Retry deployment:
   ```bash
   cdk deploy --context deployment-mode=multi-account --force
   ```

### Issue 5: Q Business Not Available

**Error Message:**
```
Q Business service not available in region
```

**Root Cause:** Q Business is not available in all AWS regions.

**Solutions:**

**Option A: Deploy in Supported Region**
```bash
export AWS_DEFAULT_REGION=us-east-1
cdk deploy --context deployment-mode=multi-account-with-qbusiness
```

**Option B: Deploy Without Q Business**
```bash
cdk deploy --context deployment-mode=multi-account
```

### Issue 6: Insufficient Permissions

**Error Message:**
```
Access denied for operation: organizations:DescribeOrganization
```

**Root Cause:** Insufficient IAM permissions.

**Solution:**
1. Ensure you're using the management account
2. Attach the following managed policies to your user/role:
   - `OrganizationsFullAccess`
   - `CloudTrailFullAccess`
   - `AmazonOpenSearchServiceFullAccess`
   - `AWSLambda_FullAccess`

## Deployment Verification

### 1. Check Stack Status
```bash
aws cloudformation describe-stacks --query 'Stacks[?contains(StackName, `Anomaly`)].{Name:StackName,Status:StackStatus}'
```

### 2. Verify CloudTrail
```bash
aws cloudtrail describe-trails --query 'trailList[?IsOrganizationTrail==`true`]'
```

### 3. Check OpenSearch Domain
```bash
aws es describe-elasticsearch-domain --domain-name <domain-name>
```

### 4. Test Lambda Functions
```bash
aws lambda list-functions --query 'Functions[?contains(FunctionName, `Anomaly`)].FunctionName'
```

## Post-Deployment Configuration

### 1. Create OpenSearch Users

1. Navigate to the Cognito User Pool (output from deployment)
2. Create users for OpenSearch dashboard access
3. Assign users to the `opensearch-admin` group

### 2. Configure Q Business (if deployed)

1. Access Q Business console
2. Configure user access through Identity Center
3. Test natural language queries

### 3. Set up Monitoring

1. Review CloudWatch dashboards
2. Configure SNS topic subscriptions for alerts
3. Test anomaly detection with sample events

## Maintenance and Updates

### Regular Maintenance
- Monitor CloudWatch metrics and logs
- Review and update anomaly detector thresholds
- Clean up old CloudTrail logs based on retention policies

### Updates
```bash
git pull origin main
cdk diff
cdk deploy
```

## Support and Troubleshooting

### Logs to Check
1. **CloudFormation Events**: For deployment issues
2. **CloudWatch Logs**: For Lambda function errors
3. **OpenSearch Logs**: For indexing and query issues
4. **CloudTrail Logs**: For API call auditing

### Getting Help
1. Check the troubleshooting section above
2. Review CloudWatch Logs for specific error messages
3. Validate prerequisites using the validation script
4. Check AWS service health dashboard

## Security Considerations

### Data Protection
- All data is encrypted in transit and at rest
- KMS keys are used for CloudTrail and S3 encryption
- OpenSearch domain uses encryption at rest

### Access Control
- IAM roles follow least privilege principle
- Cognito provides authentication for OpenSearch
- Identity Center integration for Q Business

### Network Security
- Optional VPC deployment for network isolation
- Security groups restrict access to necessary ports
- WAF can be added for additional protection

## Cost Optimization

### Monitoring Costs
- Use AWS Cost Explorer to monitor spending
- Set up billing alerts for unexpected charges
- Review OpenSearch instance types and scaling

### Optimization Tips
- Use lifecycle policies for S3 data archival
- Consider reserved instances for predictable workloads
- Optimize Lambda memory allocation based on usage
- Use appropriate OpenSearch instance types

## Conclusion

This deployment guide provides comprehensive instructions for deploying the Enhanced Multi-Account AWS Usage Anomaly Detection System. The troubleshooting section addresses common issues encountered during deployment.

For additional support or to report issues, please refer to the project repository or AWS support channels.