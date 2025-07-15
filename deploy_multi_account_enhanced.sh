#!/bin/bash

# Enhanced Multi-Account AWS Usage Anomaly Detection Deployment Script
# This script deploys the complete multi-account anomaly detection system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_MODE="multi-account"
STACK_PREFIX="MultiAccountAnomaly"
REGION=${AWS_DEFAULT_REGION:-us-east-1}

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check CDK
    if ! command -v cdk &> /dev/null; then
        print_error "AWS CDK is not installed. Please install it first."
        exit 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install it first."
        exit 1
    fi
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        print_error "Node.js is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials are not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    print_success "All prerequisites are met."
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing Python dependencies..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Install Python dependencies
    pip install -r requirements.txt
    
    print_status "Installing Node.js dependencies for Lambda functions..."
    
    # Install dependencies for CrossAccountAnomalyProcessor
    if [ -f "lambdas/CrossAccountAnomalyProcessor/package.json" ]; then
        cd lambdas/CrossAccountAnomalyProcessor
        npm install
        cd ../..
    fi
    
    print_success "Dependencies installed successfully."
}

# Function to bootstrap CDK
bootstrap_cdk() {
    print_status "Bootstrapping CDK environment..."
    
    # Get account ID
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    
    # Bootstrap CDK
    cdk bootstrap aws://${ACCOUNT_ID}/${REGION}
    
    print_success "CDK environment bootstrapped."
}

# Function to validate account permissions
validate_permissions() {
    print_status "Validating AWS account permissions..."
    
    # Check if we're in the organization management account
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    
    # Try to list organization accounts
    if aws organizations list-accounts &> /dev/null; then
        print_success "Organization management account detected."
        ORG_MANAGEMENT_ACCOUNT=true
    else
        print_warning "Not in organization management account. Some features may be limited."
        ORG_MANAGEMENT_ACCOUNT=false
    fi
    
    # Check required permissions
    REQUIRED_SERVICES=(
        "cloudformation"
        "lambda"
        "opensearch"
        "cloudwatch"
        "sns"
        "iam"
        "logs"
        "events"
    )
    
    for service in "${REQUIRED_SERVICES[@]}"; do
        if aws ${service} help &> /dev/null; then
            print_status "✓ ${service} permissions available"
        else
            print_warning "⚠ ${service} permissions may be limited"
        fi
    done
}

# Function to deploy stacks
deploy_stacks() {
    print_status "Starting multi-account deployment..."
    
    # Activate virtual environment
    source .venv/bin/activate
    
    # Set deployment context
    export CDK_CONTEXT_deployment_mode=${DEPLOYMENT_MODE}
    
    # Deploy stacks in order
    print_status "Deploying Organization Trail Stack..."
    cdk deploy OrganizationTrailStack \
        --context deployment-mode=${DEPLOYMENT_MODE} \
        --require-approval never \
        --progress events
    
    print_status "Deploying Enhanced Usage Anomaly Detector Stack..."
    cdk deploy EnhancedUsageAnomalyDetectorStack \
        --context deployment-mode=${DEPLOYMENT_MODE} \
        --require-approval never \
        --progress events
    
    print_status "Deploying Multi-Account Anomaly Stack..."
    cdk deploy MultiAccountAnomalyStack \
        --context deployment-mode=${DEPLOYMENT_MODE} \
        --require-approval never \
        --progress events
    
    # Try to deploy Q Business stack if available
    print_status "Checking Q Business availability..."
    if cdk list | grep -q "QBusinessInsightsStack"; then
        print_status "Deploying Q Business Insights Stack..."
        cdk deploy QBusinessInsightsStack \
            --context deployment-mode=${DEPLOYMENT_MODE} \
            --require-approval never \
            --progress events
        Q_BUSINESS_DEPLOYED=true
    else
        print_warning "Q Business stack not available. Requires CDK v2.110.0+"
        Q_BUSINESS_DEPLOYED=false
    fi
    
    print_success "All stacks deployed successfully!"
}

# Function to validate deployment
validate_deployment() {
    print_status "Validating deployment..."
    
    # Run validation script
    if [ -f "validate_enhanced_deployment.py" ]; then
        python3 validate_enhanced_deployment.py
    else
        print_warning "Validation script not found. Skipping validation."
    fi
}

# Function to display deployment summary
display_summary() {
    print_status "Deployment Summary"
    echo "=================================="
    
    # Get stack outputs
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    
    echo "Account ID: ${ACCOUNT_ID}"
    echo "Region: ${REGION}"
    echo "Deployment Mode: ${DEPLOYMENT_MODE}"
    echo ""
    
    # Get CloudFormation outputs
    print_status "Stack Outputs:"
    
    # Organization Trail Stack
    if aws cloudformation describe-stacks --stack-name OrganizationTrailStack &> /dev/null; then
        echo "✅ Organization Trail Stack: Deployed"
        TRAIL_ARN=$(aws cloudformation describe-stacks \
            --stack-name OrganizationTrailStack \
            --query 'Stacks[0].Outputs[?OutputKey==`OrganizationTrailArn`].OutputValue' \
            --output text 2>/dev/null || echo "Not available")
        echo "   Trail ARN: ${TRAIL_ARN}"
    fi
    
    # Enhanced Usage Anomaly Detector Stack
    if aws cloudformation describe-stacks --stack-name EnhancedUsageAnomalyDetectorStack &> /dev/null; then
        echo "✅ Enhanced Usage Anomaly Detector Stack: Deployed"
        OPENSEARCH_ENDPOINT=$(aws cloudformation describe-stacks \
            --stack-name EnhancedUsageAnomalyDetectorStack \
            --query 'Stacks[0].Outputs[?OutputKey==`OpenSearchDomainEndpoint`].OutputValue' \
            --output text 2>/dev/null || echo "Not available")
        echo "   OpenSearch Endpoint: ${OPENSEARCH_ENDPOINT}"
    fi
    
    # Multi-Account Anomaly Stack
    if aws cloudformation describe-stacks --stack-name MultiAccountAnomalyStack &> /dev/null; then
        echo "✅ Multi-Account Anomaly Stack: Deployed"
        DASHBOARD_NAME=$(aws cloudformation describe-stacks \
            --stack-name MultiAccountAnomalyStack \
            --query 'Stacks[0].Outputs[?OutputKey==`MonitoringDashboardName`].OutputValue' \
            --output text 2>/dev/null || echo "Not available")
        echo "   Dashboard: ${DASHBOARD_NAME}"
        
        SNS_TOPIC=$(aws cloudformation describe-stacks \
            --stack-name MultiAccountAnomalyStack \
            --query 'Stacks[0].Outputs[?OutputKey==`SystemAlertsTopicArn`].OutputValue' \
            --output text 2>/dev/null || echo "Not available")
        echo "   Alerts Topic: ${SNS_TOPIC}"
    fi
    
    # Q Business Stack
    if [ "${Q_BUSINESS_DEPLOYED}" = true ]; then
        echo "✅ Q Business Insights Stack: Deployed"
        Q_APP_ID=$(aws cloudformation describe-stacks \
            --stack-name QBusinessInsightsStack \
            --query 'Stacks[0].Outputs[?OutputKey==`QBusinessApplicationId`].OutputValue' \
            --output text 2>/dev/null || echo "Not available")
        echo "   Q Business App ID: ${Q_APP_ID}"
    else
        echo "⚠️  Q Business Insights Stack: Not deployed"
    fi
    
    echo ""
    print_status "Next Steps:"
    echo "1. Subscribe to SNS alerts: ${SNS_TOPIC}"
    echo "2. Access CloudWatch Dashboard: ${DASHBOARD_NAME}"
    echo "3. Configure OpenSearch dashboards: ${OPENSEARCH_ENDPOINT}"
    if [ "${Q_BUSINESS_DEPLOYED}" = true ]; then
        echo "4. Set up Q Business users and permissions"
    fi
    echo "5. Test anomaly detection with sample events"
    
    echo ""
    print_success "Multi-Account Anomaly Detection System is ready!"
}

# Function to handle cleanup on error
cleanup_on_error() {
    print_error "Deployment failed. Cleaning up..."
    
    # Optionally destroy stacks on failure
    read -p "Do you want to destroy partially deployed stacks? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Destroying stacks..."
        cdk destroy --all --force
    fi
}

# Main deployment function
main() {
    echo "🚀 Enhanced Multi-Account AWS Usage Anomaly Detection Deployment"
    echo "================================================================"
    
    # Set up error handling
    trap cleanup_on_error ERR
    
    # Run deployment steps
    check_prerequisites
    validate_permissions
    install_dependencies
    bootstrap_cdk
    deploy_stacks
    validate_deployment
    display_summary
    
    print_success "Deployment completed successfully! 🎉"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --validate     Only run validation"
        echo "  --cleanup      Clean up deployed resources"
        echo ""
        echo "Environment Variables:"
        echo "  AWS_DEFAULT_REGION    AWS region (default: us-east-1)"
        echo ""
        exit 0
        ;;
    --validate)
        validate_deployment
        exit 0
        ;;
    --cleanup)
        print_warning "This will destroy all deployed stacks!"
        read -p "Are you sure? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            source .venv/bin/activate
            cdk destroy --all --force
            print_success "Cleanup completed."
        fi
        exit 0
        ;;
    "")
        main
        ;;
    *)
        print_error "Unknown option: $1"
        echo "Use --help for usage information."
        exit 1
        ;;
esac