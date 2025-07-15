# Troubleshooting Guide - Enhanced Multi-Account AWS Usage Anomaly Detection

## Common Issues and Solutions

### 1. Environment and Prerequisites Issues

#### Python Version Warnings
**Issue**: `WARNING: You are using python release 3.7.16, which has reached end-of-life!`

**Solution**: 
- **Recommended**: Upgrade to Python 3.8+
- **Workaround**: The system still works with Python 3.7, warnings can be ignored

```bash
# Check Python version
python3 --version

# Upgrade Python (varies by system)
# Ubuntu/Debian:
sudo apt update && sudo apt install python3.8

# macOS with Homebrew:
brew install python@3.8
```

#### Node.js Version Warnings
**Issue**: `Node 17 has reached end-of-life and is not supported`

**Solution**:
- **Recommended**: Upgrade to Node.js 18+
- **Workaround**: The system still works with Node 17, warnings can be ignored

```bash
# Check Node version
node --version

# Upgrade Node.js using nvm
nvm install 18
nvm use 18
```

#### CDK Version Issues
**Issue**: Q Business resources fail to create due to old CDK version

**Solution**:
```bash
# Upgrade CDK
pip3 install --upgrade 'aws-cdk-lib>=2.110.0'

# Verify version
python3 -c "from infra.multi_account.check_q_business import get_q_business_status; print(get_q_business_status())"
```

### 2. Deployment Issues

#### Stack Creation Failures
**Issue**: CloudFormation stacks fail to create

**Common Causes and Solutions**:

1. **Insufficient Permissions**
   ```bash
   # Verify your AWS permissions
   aws sts get-caller-identity
   aws iam get-user
   ```
   **Solution**: Ensure your AWS credentials have administrative permissions

2. **Resource Limits**
   ```bash
   # Check service quotas
   aws service-quotas list-service-quotas --service-code opensearch
   ```
   **Solution**: Request quota increases if needed

3. **Region Availability**
   **Solution**: Ensure all services are available in your target region

#### Organization Trail Issues
**Issue**: `Trail creation failed - not an organization management account`

**Solution**: 
- Deploy from the AWS Organizations management account
- Or modify the trail to be a regular trail instead of organization-wide

#### OpenSearch Domain Creation Failures
**Issue**: OpenSearch domain fails to create

**Common Solutions**:
1. **Instance Type Availability**: Try different instance types
2. **AZ Availability**: Reduce availability zones from 3 to 2
3. **VPC Limits**: Ensure sufficient IP addresses in subnets

```bash
# Check available instance types
aws opensearch describe-instance-types --region us-east-1
```

### 3. Q Business Integration Issues

#### Q Business Application Creation Fails
**Issue**: `AWS::QBusiness::Application` resource fails

**Solutions**:
1. **Service Availability**: Ensure Q Business is available in your region
2. **Identity Center**: Verify AWS Identity Center is set up
3. **Permissions**: Check Q Business service permissions

```bash
# Check Q Business availability
aws qbusiness list-applications --region us-east-1
```

#### Identity Center Issues
**Issue**: Identity Center integration fails

**Solutions**:
1. **Enable Identity Center**: Set up AWS Identity Center in your account
2. **Permissions**: Ensure proper IAM permissions for Identity Center
3. **Region**: Use a region where Identity Center is available

### 4. Lambda Function Issues

#### Lambda Deployment Failures
**Issue**: Lambda functions fail to deploy

**Common Solutions**:
1. **Package Size**: Ensure Lambda packages are under size limits
2. **Dependencies**: Check all dependencies are included
3. **Runtime**: Verify runtime compatibility

```bash
# Check Lambda function logs
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/"
```

#### Lambda Function Errors
**Issue**: Lambda functions throw runtime errors

**Debugging Steps**:
1. Check CloudWatch Logs
2. Verify environment variables
3. Test function permissions

```bash
# View Lambda function logs
aws logs tail /aws/lambda/your-function-name --follow
```

### 5. OpenSearch Issues

#### OpenSearch Access Issues
**Issue**: Cannot access OpenSearch dashboards

**Solutions**:
1. **Cognito Setup**: Verify Cognito user pool configuration
2. **User Creation**: Create users in Cognito
3. **Role Mapping**: Check IAM role mappings in OpenSearch

```bash
# Check OpenSearch domain status
aws opensearch describe-domain --domain-name usage-anomaly-detector-os
```

#### Anomaly Detector Issues
**Issue**: Anomaly detectors not working

**Solutions**:
1. **Data Ingestion**: Verify CloudTrail logs are being indexed
2. **Detector Configuration**: Check detector settings
3. **Index Patterns**: Ensure correct index patterns

### 6. CloudTrail Issues

#### CloudTrail Not Logging
**Issue**: CloudTrail appears inactive

**Solutions**:
1. **Trail Status**: Check if trail is enabled
2. **Permissions**: Verify CloudTrail permissions
3. **S3 Bucket**: Check S3 bucket permissions

```bash
# Check CloudTrail status
aws cloudtrail get-trail-status --name your-trail-name
```

#### Missing Events
**Issue**: Expected events not appearing in logs

**Solutions**:
1. **Event Types**: Verify management vs data events configuration
2. **Regions**: Check multi-region trail settings
3. **Filters**: Review event selectors

### 7. Networking and Connectivity Issues

#### VPC Configuration Issues
**Issue**: Resources cannot communicate

**Solutions**:
1. **Security Groups**: Check security group rules
2. **NACLs**: Verify network ACL settings
3. **Route Tables**: Check routing configuration

#### DNS Resolution Issues
**Issue**: Cannot resolve service endpoints

**Solutions**:
1. **VPC DNS**: Enable DNS resolution in VPC
2. **Route 53**: Check private hosted zones
3. **Endpoints**: Use VPC endpoints for AWS services

### 8. Performance Issues

#### Slow Query Performance
**Issue**: OpenSearch queries are slow

**Solutions**:
1. **Index Optimization**: Optimize index settings
2. **Shard Configuration**: Adjust shard count
3. **Instance Sizing**: Scale up OpenSearch instances

#### High Lambda Costs
**Issue**: Lambda functions consuming too many resources

**Solutions**:
1. **Memory Optimization**: Adjust memory allocation
2. **Timeout Settings**: Optimize timeout values
3. **Concurrency**: Set reserved concurrency limits

### 9. Monitoring and Alerting Issues

#### Missing Alerts
**Issue**: Not receiving anomaly alerts

**Solutions**:
1. **SNS Subscriptions**: Confirm email subscriptions
2. **Topic Permissions**: Check SNS topic permissions
3. **Detector Thresholds**: Adjust anomaly thresholds

#### False Positives
**Issue**: Too many false positive alerts

**Solutions**:
1. **Threshold Tuning**: Adjust detector sensitivity
2. **Baseline Period**: Increase training period
3. **Filters**: Add event filters to reduce noise

### 10. Cost Optimization Issues

#### Unexpected Costs
**Issue**: Higher than expected AWS costs

**Solutions**:
1. **Resource Sizing**: Right-size OpenSearch instances
2. **Data Retention**: Implement lifecycle policies
3. **Reserved Instances**: Use reserved capacity for predictable workloads

## Diagnostic Commands

### General Health Check
```bash
# Run deployment validation
python3 validate_deployment.py -r us-east-1

# Check all stack statuses
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE
```

### OpenSearch Diagnostics
```bash
# Check domain health
aws opensearch describe-domain --domain-name usage-anomaly-detector-os

# List indices
curl -X GET "https://your-opensearch-endpoint/_cat/indices?v"

# Check anomaly detectors
curl -X GET "https://your-opensearch-endpoint/_plugins/_anomaly_detection/detectors"
```

### CloudTrail Diagnostics
```bash
# List trails
aws cloudtrail describe-trails

# Check trail status
aws cloudtrail get-trail-status --name your-trail-name

# Verify recent events
aws cloudtrail lookup-events --max-items 10
```

### Lambda Diagnostics
```bash
# List functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `anomaly`)]'

# Check function configuration
aws lambda get-function --function-name your-function-name

# View recent invocations
aws logs filter-log-events --log-group-name /aws/lambda/your-function-name --start-time $(date -d '1 hour ago' +%s)000
```

## Getting Help

### AWS Support Resources
- **AWS Support Center**: For account-specific issues
- **AWS re:Post**: Community-driven Q&A
- **AWS Documentation**: Service-specific guides
- **AWS Trusted Advisor**: Automated recommendations

### Community Resources
- **GitHub Issues**: Report bugs and feature requests
- **Stack Overflow**: Technical questions with AWS tags
- **AWS User Groups**: Local community meetups
- **AWS Forums**: Service-specific discussions

### Professional Services
- **AWS Professional Services**: Implementation assistance
- **AWS Partner Network**: Certified consultants
- **Third-party Specialists**: Security and monitoring experts

## Emergency Procedures

### System Down
1. **Check AWS Service Health**: https://status.aws.amazon.com/
2. **Verify Credentials**: Ensure AWS credentials are valid
3. **Check Quotas**: Verify service limits haven't been exceeded
4. **Review Recent Changes**: Check CloudTrail for recent modifications

### Data Loss Prevention
1. **Enable Versioning**: S3 bucket versioning for trail logs
2. **Cross-Region Backup**: Replicate critical data
3. **Snapshot Strategy**: Regular OpenSearch snapshots
4. **Configuration Backup**: Store CloudFormation templates in version control

### Rollback Procedures
1. **Stack Rollback**: Use CloudFormation rollback features
2. **Configuration Restore**: Revert to known good configurations
3. **Data Recovery**: Restore from backups if needed
4. **Service Restart**: Restart services in correct order

## Prevention Best Practices

### Monitoring
- Set up comprehensive CloudWatch alarms
- Monitor AWS service quotas
- Track cost and usage patterns
- Implement automated health checks

### Security
- Regular security assessments
- Principle of least privilege
- Enable AWS Config for compliance
- Use AWS Security Hub for centralized security

### Maintenance
- Regular updates to CDK and dependencies
- Periodic review of configurations
- Performance optimization reviews
- Cost optimization assessments

### Documentation
- Keep deployment procedures updated
- Document custom configurations
- Maintain troubleshooting runbooks
- Record lessons learned from incidents