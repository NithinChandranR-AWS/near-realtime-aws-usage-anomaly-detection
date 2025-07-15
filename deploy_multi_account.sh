#!/bin/bash

# Multi-Account AWS Usage Anomaly Detection with Q Business Deployment Script
# This script deploys the enhanced multi-account anomaly detection system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
OPENSEARCH_VERSION="OPENSEARCH_2_9"
ENABLE_LAMBDA_TRAIL="true"
DEPLOYMENT_MODE="multi-account"
EMAIL=""
REGION=""

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
    
    # Check if CDK is installed
    if ! command -v cdk &> /dev/null; then
        print_error "AWS CDK is not installed. Please install it first."
        exit 1
    fi
    
    # Check CDK version
    CDK_VERSION=$(cdk --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
    print_status "CDK Version: $CDK_VERSION"
    
    # Check if AWS CLI is configured
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS CLI is not configured or credentials are invalid."
        exit 1
    fi
    
    # Get current account and region
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    if [ -z "$REGION" ]; then
        REGION=$(aws configure get region)
        if [ -z "$REGION" ]; then
            REGION="us-east-1"
            print_warning "No region configured, using default: $REGION"
        fi
    fi
    
    print_status "Account ID: $ACCOUNT_ID"
    print_status "Region: $REGION"
    
    # Check if this is an organization management account
    ORG_STATUS=$(aws organizations describe-organization --query 'Organization.MasterAccountId' --output text 2>/dev/null || echo "NOT_ORG_ACCOUNT")
    if [ "$ORG_STATUS" = "NOT_ORG_ACCOUNT" ]; then
        print_warning "This account is not part of an AWS Organization or you don't have permissions."
        print_warning "Organization trail will be created as a regular trail."
    else
        print_status "Organization management account detected: $ORG_STATUS"
    fi
    
    # Check Python version
    PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
    if [[ $(echo "$PYTHON_VERSION < 3.8" | bc -l) -eq 1 ]]; then
        print_warning "Python version $PYTHON_VERSION is below recommended 3.8+"
        print_warning "Some features may not work as expected"
    fi
    
    # Check Node version
    NODE_VERSION=$(node --version 2>&1 | grep -oE '[0-9]+' | head -1)
    if [[ $NODE_VERSION -lt 18 ]]; then
        print_warning "Node.js version $NODE_VERSION is below recommended 18+"
        print_warning "Lambda functions may not work as expected"
    fi
}

# Function to install dependencies
install_dependencies() {
    print_status "Installing Python dependencies..."
    
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt --user
    fi
    
    if [ -f "shared/python/requirements.txt" ]; then
        print_status "Installing Lambda layer dependencies..."
        pip3 install -r shared/python/requirements.txt -t shared/python --user
    fi
    
    print_success "Dependencies installed successfully"
}

# Function to validate parameters
validate_parameters() {
    if [ -z "$EMAIL" ]; then
        print_error "Email address is required for alerts"
        echo "Usage: $0 --email your-email@example.com [options]"
        exit 1
    fi
    
    # Validate email format
    if [[ ! "$EMAIL" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        print_error "Invalid email format: $EMAIL"
        exit 1
    fi
    
    print_status "Using email: $EMAIL"
    print_status "OpenSearch version: $OPENSEARCH_VERSION"
    print_status "Lambda trail enabled: $ENABLE_LAMBDA_TRAIL"
}

# Function to deploy stacks
deploy_stacks() {
    print_status "Starting multi-account deployment..."
    
    # Set environment variables
    export AWS_REGION=$REGION
    
    # Deploy all stacks
    print_status "Deploying all stacks with dependencies..."
    
    cdk deploy \
        --app "python3 app_enhanced_test.py" \
        --context deployment-mode=$DEPLOYMENT_MODE \
        --context opensearch-version=$OPENSEARCH_VERSION \
        --context enable-lambda-trail=$ENABLE_LAMBDA_TRAIL \
        --parameters EnhancedUsageAnomalyDetectorStack:opensearchalertemail=$EMAIL \
        --all \
        --require-approval never \
        --outputs-file cdk-outputs.json
    
    if [ $? -eq 0 ]; then
        print_success "Deployment completed successfully!"
    else
        print_error "Deployment failed!"
        exit 1
    fi
}

# Function to display deployment results
display_results() {
    print_status "Deployment Summary:"
    echo "===================="
    
    if [ -f "cdk-outputs.json" ]; then
        print_status "Stack outputs saved to: cdk-outputs.json"
        
        # Extract key outputs
        OPENSEARCH_ENDPOINT=$(jq -r '.EnhancedUsageAnomalyDetectorStack."Opensearch dashboard endpoint" // empty' cdk-outputs.json 2>/dev/null)
        USER_CREATE_URL=$(jq -r '.EnhancedUsageAnomalyDetectorStack."Opensearch create user url" // empty' cdk-outputs.json 2>/dev/null)
        Q_APP_ID=$(jq -r '.QBusinessInsightsStack.QApplicationId // empty' cdk-outputs.json 2>/dev/null)
        
        if [ ! -z "$OPENSEARCH_ENDPOINT" ]; then
            print_success "OpenSearch Dashboard: $OPENSEARCH_ENDPOINT"
        fi
        
        if [ ! -z "$USER_CREATE_URL" ]; then
            print_success "Create OpenSearch User: $USER_CREATE_URL"
        fi
        
        if [ ! -z "$Q_APP_ID" ]; then
            print_success "Q Business Application ID: $Q_APP_ID"
        fi
    fi
    
    echo ""
    print_status "Next Steps:"
    echo "1. Create an OpenSearch user using the provided URL"
    echo "2. Access the OpenSearch dashboard to view anomaly detectors"
    echo "3. Configure Q Business users in Identity Center (if deployed)"
    echo "4. Test the system by generating some AWS API activity"
    echo ""
    print_status "For troubleshooting, check the deployment logs above and CloudFormation console"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 --email <email> [options]"
    echo ""
    echo "Required:"
    echo "  --email <email>              Email address for anomaly alerts"
    echo ""
    echo "Optional:"
    echo "  --region <region>            AWS region (default: from AWS config)"
    echo "  --opensearch-version <ver>   OpenSearch version (default: OPENSEARCH_2_9)"
    echo "  --disable-lambda-trail       Disable Lambda data events in CloudTrail"
    echo "  --help                       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --email admin@company.com"
    echo "  $0 --email admin@company.com --region us-west-2"
    echo "  $0 --email admin@company.com --opensearch-version OPENSEARCH_2_7"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --email)
            EMAIL="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --opensearch-version)
            OPENSEARCH_VERSION="$2"
            shift 2
            ;;
        --disable-lambda-trail)
            ENABLE_LAMBDA_TRAIL="false"
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    print_status "🚀 AWS Multi-Account Usage Anomaly Detection Deployment"
    print_status "========================================================"
    
    validate_parameters
    check_prerequisites
    install_dependencies
    deploy_stacks
    display_results
    
    print_success "🎉 Multi-account anomaly detection system deployed successfully!"
}

# Run main function
main