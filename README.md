# Enhanced Multi-Account AWS Usage Anomaly Detection

This project implements a comprehensive multi-account AWS usage anomaly detection system with AI-powered natural language insights. The system monitors AWS API calls across your entire organization, detects unusual patterns, and provides intelligent analysis through Amazon Q for Business integration.

## 🚀 Features

### Multi-Account Support
- **Organization-wide monitoring** across all AWS accounts
- **Account-aware anomaly detection** with context-specific thresholds
- **Cross-account correlation** to detect organization-wide patterns
- **Centralized management** from the organization management account

### AI-Powered Insights
- **Amazon Q for Business integration** for natural language queries
- **Intelligent anomaly analysis** with root cause suggestions
- **Cost impact analysis** with optimization recommendations
- **Natural language alerts** for both technical and business stakeholders

### Advanced Anomaly Detection
- **Multi-service support**: EC2, Lambda, EBS, and more
- **Account type-aware thresholds** (production vs development)
- **Real-time processing** with sub-5-minute latency
- **Enhanced severity calculation** based on multiple factors

### Comprehensive Monitoring
- **Real-time dashboards** with system health metrics
- **Proactive alerting** with SNS notifications
- **System health monitoring** with automated diagnostics
- **Custom metrics** and performance tracking

## 🏗️ Architecture

The system uses a hub-and-spoke architecture with the following components:

1. **Organization Trail**: Centralized CloudTrail for all accounts
2. **Multi-Account Processor**: Enhanced Lambda for account-aware processing
3. **OpenSearch Domain**: High-performance anomaly storage and analysis
4. **Amazon Q for Business**: Natural language insights and querying
5. **Account Enrichment Service**: Metadata caching with Organizations API
6. **Monitoring Stack**: Comprehensive dashboards and alerting

## 📋 Prerequisites

- AWS CLI configured with organization management account access
- AWS CDK v2.110.0 or later
- Python 3.8+ (Python 3.7 supported but deprecated)
- Node.js 18.x or later
- AWS Organizations enabled (for multi-account features)

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone <repository-url>
cd enhanced-multi-account-anomaly-detection
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Deploy Multi-Account System
```bash
# Deploy with full multi-account and Q Business support
./deploy_multi_account_enhanced.sh

# Or deploy with CDK directly
cdk deploy --context deployment-mode=multi-account --all
```

### 3. Validate Deployment
```bash
python validate_enhanced_deployment.py
```

## 🔧 Deployment Modes

The system supports three deployment modes:

### Multi-Account Mode (Recommended)
```bash
cdk deploy --context deployment-mode=multi-account --all
```
- Full organization-wide monitoring
- Amazon Q for Business integration
- Cross-account anomaly correlation
- Enhanced dashboards and alerting

### Single-Account with Q Business
```bash
cdk deploy --context deployment-mode=single-account-with-qbusiness --all
```
- Single account monitoring
- Amazon Q for Business integration
- Natural language insights

### Single-Account (Legacy)
```bash
cdk deploy
```
- Basic single account monitoring
- Backward compatibility mode

## 📊 Monitoring and Dashboards

### CloudWatch Dashboards
Access your monitoring dashboard at:
```
https://console.aws.amazon.com/cloudwatch/home#dashboards:name=Multi-Account-Anomaly-Detection-System
```

### Key Metrics
- **System Health Score**: Overall system health (0-100)
- **Processing Latency**: Event processing time
- **Account Enrichment Rate**: Metadata enrichment success
- **Anomaly Detection Accuracy**: False positive/negative rates

### Amazon Q for Business Queries
Example natural language queries:
- "Show me EC2 anomalies from the last 24 hours"
- "What caused the spike in Lambda invocations yesterday?"
- "Analyze cost impact of recent EBS volume creation anomalies"

## ⚙️ Configuration

### Environment Variables
Key configuration options:

```bash
# Anomaly detection sensitivity
ANOMALY_THRESHOLD=3

# Account metadata cache TTL
CACHE_TTL_HOURS=24

# Enable cost analysis
ENABLE_COST_ANALYSIS=true

# Enable root cause analysis
ENABLE_ROOT_CAUSE_ANALYSIS=true
```

### Account Type Classification
The system automatically classifies accounts based on naming patterns:
- **Production**: Contains "prod", "production", "prd"
- **Staging**: Contains "stag", "staging", "stage"
- **Development**: Contains "dev", "development", "develop"
- **Testing**: Contains "test", "testing", "qa"
- **Sandbox**: Contains "sandbox", "sb", "demo"

## 🔒 Security

### Data Protection
- **Encryption at rest**: KMS encryption for all stored data
- **Encryption in transit**: TLS 1.2+ for all communications
- **IAM least privilege**: Minimal required permissions
- **VPC deployment**: Optional network isolation

### Access Control
- **Identity Center integration**: Centralized user management
- **Fine-grained permissions**: Resource-level access control
- **Audit logging**: Comprehensive activity tracking

## 💰 Cost Optimization

### Built-in Cost Controls
- **Lifecycle policies**: Automatic data retention management
- **Serverless architecture**: Pay-per-use pricing model
- **Efficient caching**: Reduced API calls and processing
- **Cost analysis integration**: Real-time cost impact assessment

### Estimated Costs
For a typical organization with 50 accounts:
- **Lambda**: ~$50-100/month
- **OpenSearch**: ~$200-400/month
- **CloudTrail**: ~$10-20/month
- **Storage**: ~$20-50/month

## 🛠️ Troubleshooting

### Common Issues

#### High Lambda Costs
```bash
# Check processing metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=MultiAccountLogsFunction
```

#### Missing Account Metadata
```bash
# Refresh account cache
aws lambda invoke \
  --function-name AccountEnrichmentFunction \
  --payload '{"action": "refresh_cache"}'
```

#### Q Business Integration Issues
```bash
# Validate Q Business setup
python validate_enhanced_deployment.py --q-business-only
```

### Debug Mode
Enable detailed logging:
```bash
export LOG_LEVEL=DEBUG
export ENABLE_DETAILED_METRICS=true
```

## 🧪 Testing

### Run Unit Tests
```bash
python -m pytest tests/unit/ -v
```

### Run Integration Tests
```bash
python -m pytest tests/integration/ -v
```

### Validate Infrastructure
```bash
python tests/infrastructure_validation.py
```

## 📚 Documentation

- [Deployment Guide](DEPLOYMENT_GUIDE_ENHANCED.md)
- [Architecture Overview](docs/enhanced-architecture.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and development process.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For issues and questions:
- Check the [Troubleshooting Guide](TROUBLESHOOTING.md)
- Review [GitHub Issues](https://github.com/your-org/enhanced-anomaly-detection/issues)
- Consult the [Documentation](docs/)

## 🎯 Roadmap

- [ ] **Machine Learning Integration**: Advanced anomaly detection with SageMaker
- [ ] **Multi-Region Support**: Cross-region anomaly correlation
- [ ] **Custom Connectors**: Integration with third-party SIEM tools
- [ ] **Mobile Dashboard**: React Native mobile application
- [ ] **Automated Remediation**: Self-healing capabilities for common issues

---

**Built with ❤️ for AWS Organizations seeking intelligent anomaly detection and cost optimization.**