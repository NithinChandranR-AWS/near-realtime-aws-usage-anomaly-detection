# Multi-Account AWS Usage Anomaly Detection System

A comprehensive solution for detecting usage anomalies across multiple AWS accounts with natural language insights powered by Amazon Q for Business.

> **AWS Sample**: This repository demonstrates best practices for implementing multi-account anomaly detection. Please review and customize according to your specific requirements before deploying in production.

## 🏗️ Architecture

![Architecture Overview](docs/architecture.md)

The solution provides:
- **Multi-account monitoring** across AWS Organizations
- **Real-time anomaly detection** for EC2, Lambda, and EBS usage
- **Natural language insights** through Amazon Q for Business
- **Comprehensive alerting** with contextual information

## 🚀 Quick Start

### Prerequisites

- AWS Organizations enabled with management account access
- AWS CDK v2.110.0 or higher
- Python 3.8+ and Node.js 18+
- Appropriate IAM permissions for deployment

### Deployment

1. **Clone the repository**:
   ```bash
   git clone https://github.com/aws-samples/multi-account-anomaly-detection.git
   cd multi-account-anomaly-detection
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Deploy the solution**:
   ```bash
   # For new organization trail
   ./deploy_multi_account_enhanced.sh
   
   # For existing organization trail
   cdk deploy --context use-existing-trail=true --context existing-log-group-name=YOUR_LOG_GROUP_NAME --all
   ```

4. **Validate deployment**:
   ```bash
   python validate_enhanced_deployment.py
   ```

## 📊 Features

### Multi-Account Support
- Organization-wide CloudTrail integration
- Cross-account anomaly detection with account categorization
- Account metadata enrichment using AWS Organizations API
- Support for existing organization trails

### Amazon Q for Business Integration
- Natural language query interface for anomaly insights
- Identity Center integration for secure access control
- Automated anomaly data synchronization
- Cost impact analysis and security recommendations

### Enhanced Monitoring
- Real-time CloudWatch dashboards
- Comprehensive error handling with retry logic
- Dead letter queue processing for failed events
- System health monitoring with automated checks

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `deployment-mode` | Deployment mode (single-account/multi-account) | single-account |
| `use-existing-trail` | Use existing organization trail | false |
| `existing-log-group-name` | Existing CloudTrail log group name | aws-cloudtrail-logs-ACCOUNT-ID-RANDOM |

### Account Type Configuration

Tag your AWS accounts using AWS Organizations:

```json
{
  "AccountType": "production|staging|development",
  "Environment": "prod|staging|dev",
  "CostCenter": "engineering|security|operations"
}
```

### Anomaly Thresholds

Customize thresholds in `lambdas/CrossAccountAnomalyProcessor/config.py`:

```python
THRESHOLDS = {
    'production': {'ec2': 10, 'lambda': 1000, 'ebs': 20},
    'staging': {'ec2': 5, 'lambda': 500, 'ebs': 10},
    'development': {'ec2': 2, 'lambda': 100, 'ebs': 5}
}
```

## 📈 Monitoring

### CloudWatch Dashboard
Access the monitoring dashboard in the AWS Console under CloudWatch > Dashboards > "MultiAccountAnomalyDetection"

### SNS Alerts
Subscribe to system alerts:
```bash
aws sns subscribe \
  --topic-arn <SystemAlertsTopicArn> \
  --protocol email \
  --notification-endpoint your-email@example.com
```

### Custom Metrics
The system publishes metrics to the `MultiAccountAnomalyDetection` namespace:
- `OverallHealthScore`: System health percentage (0-100)
- `ProcessingSuccessRate`: Event processing success rate
- `LambdaErrorRate`: Lambda function error rates

## 🤖 Amazon Q for Business

### Natural Language Queries
Example queries you can ask Q Business:
- "Show me EC2 anomalies from the last 24 hours"
- "What accounts had the highest cost impact this week?"
- "Are there any security concerns with recent Lambda anomalies?"
- "Compare anomaly patterns between production and staging accounts"

### Setup
1. Identity Center is automatically configured during deployment
2. Add users to the "QBusinessAdmins" group for access
3. Access Q Business through the AWS Console

## 🔍 Troubleshooting

### Common Issues

1. **CDK Version Compatibility**:
   ```bash
   npm install -g aws-cdk@latest
   pip install -r requirements.txt --upgrade
   ```

2. **Organization Permissions**:
   ```bash
   aws organizations list-accounts
   ```

3. **Validation**:
   ```bash
   python validate_enhanced_deployment.py
   ```

For detailed troubleshooting, see [troubleshooting.md](troubleshooting.md).

## 🔒 Security

The solution implements security best practices:
- **Least privilege IAM roles** for all components
- **Identity Center integration** for Q Business access
- **KMS encryption** for data at rest and in transit
- **VPC deployment options** for network isolation
- **Comprehensive audit logging**

## 📄 Documentation

- [Architecture Overview](docs/architecture.md)
- [Deployment Guide](deployment-guide.md)
- [Troubleshooting Guide](troubleshooting.md)
- [Enhancement Summary](enhancement-summary.md)

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](contributing.md) for details.

## 📄 License

This project is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This is a sample implementation for demonstration purposes. Please review the code and customize it according to your specific security and compliance requirements before deploying in production environments.

---

**AWS Sample** | **Multi-Account Anomaly Detection** | **Amazon Q for Business Integration**