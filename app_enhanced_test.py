#!/usr/bin/env python3
import os
import aws_cdk as cdk
from infra.usage_anomaly_detector import UsageAnomalyDetectorStack
from infra.multi_account.organization_trail_stack import OrganizationTrailStack
from infra.multi_account.enhanced_anomaly_detector_stack_test import EnhancedAnomalyDetectorStack

# Check if Q Business is available
try:
    from infra.multi_account.q_business_stack import QBusinessStack
    q_business_available = True
except ImportError:
    q_business_available = False

app = cdk.App()

# Get deployment mode from context
deployment_mode = app.node.try_get_context("deployment-mode") or "single-account"

if deployment_mode == "multi-account":
    print("Deploying in multi-account mode with enhanced features...")
    
    # Check if we should use existing organization trail
    use_existing_trail = app.node.try_get_context("use-existing-trail") or False
    
    if use_existing_trail:
        print("Using existing organization trail...")
        # Import existing log group
        from aws_cdk import aws_logs as logs
        # Import existing log group - replace with your actual log group name
        existing_log_group_name = app.node.try_get_context("existing-log-group-name") or "aws-cloudtrail-logs-ACCOUNT-ID-RANDOM"
        existing_log_group = logs.LogGroup.from_log_group_name(
            app, "ExistingOrgTrailLogGroup", 
            existing_log_group_name
        )
        
        # Deploy the base anomaly detector stack
        base_stack = UsageAnomalyDetectorStack(
            app,
            "EnhancedUsageAnomalyDetectorStack",
            description="Enhanced AWS usage anomaly detector with multi-account support"
        )
        
        # Deploy enhanced anomaly detector with multi-account support using existing trail
        enhanced_stack = EnhancedAnomalyDetectorStack(
            app,
            "MultiAccountAnomalyStack",
            log_group=existing_log_group,
            opensearch_domain=getattr(base_stack, 'domain', None),
            description="Multi-account anomaly detection with natural language insights"
        )
        enhanced_stack.add_dependency(base_stack)
    else:
        # Deploy organization trail stack (in management account)
        org_trail_stack = OrganizationTrailStack(
            app,
            "OrganizationTrailStack",
            description="Organization-wide CloudTrail for multi-account anomaly detection"
        )
        
        # Deploy the base anomaly detector stack
        base_stack = UsageAnomalyDetectorStack(
            app,
            "EnhancedUsageAnomalyDetectorStack",
            description="Enhanced AWS usage anomaly detector with multi-account support"
        )
        
        # Deploy enhanced anomaly detector with multi-account support
        enhanced_stack = EnhancedAnomalyDetectorStack(
            app,
            "MultiAccountAnomalyStack",
            log_group=org_trail_stack.log_group,
            opensearch_domain=getattr(base_stack, 'domain', None),
            description="Multi-account anomaly detection with natural language insights"
        )
        enhanced_stack.add_dependency(org_trail_stack)
        enhanced_stack.add_dependency(base_stack)
    
    # Deploy Amazon Q for Business stack if available
    if q_business_available and hasattr(enhanced_stack, 'q_connector_function'):
        q_business_stack = QBusinessStack(
            app,
            "QBusinessInsightsStack",
            q_connector_function=enhanced_stack.q_connector_function,
            description="Amazon Q for Business for natural language anomaly insights"
        )
        q_business_stack.add_dependency(enhanced_stack)
    
    # Output deployment summary
    print("\n🚀 Enhanced Multi-Account Deployment Summary:")
    print("=" * 50)
    print("✅ Organization Trail: Centralized logging across all accounts")
    print("✅ Enhanced OpenSearch: Multi-account anomaly detection")
    print("✅ Cross-Account Dashboards: Unified visibility")
    if q_business_available:
        print("✅ Q Business Integration: Natural language insights enabled")
    else:
        print("⚠️  Q Business Integration: Requires CDK v2.110.0+ (run: pip install -r requirements.txt)")
    print("=" * 50)
    
else:
    print("Deploying in single-account mode...")
    
    # Deploy standard single-account stack
    UsageAnomalyDetectorStack(
        app,
        "UsageAnomalyDetectorStack",
        description="AWS usage anomaly detector for single account"
    )

app.synth()
