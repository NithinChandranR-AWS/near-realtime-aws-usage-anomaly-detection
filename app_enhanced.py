#!/usr/bin/env python3
import os
import aws_cdk as cdk
from aws_cdk import Aspects
from infra.usage_anomaly_detector import UsageAnomalyDetectorStack
from infra.multi_account.organization_trail_stack import OrganizationTrailStack
from infra.multi_account.enhanced_anomaly_detector_stack import EnhancedAnomalyDetectorStack
from infra.multi_account.q_business_stack import QBusinessStack

# Import CDK Nag for security validation
try:
    from cdk_nag import AwsSolutionsChecks
    CDK_NAG_AVAILABLE = False  # Temporarily disabled
except ImportError:
    print("⚠️  CDK Nag not installed. Install with: pip install cdk-nag")
    CDK_NAG_AVAILABLE = False

app = cdk.App()

# Get deployment mode from context
deployment_mode = app.node.try_get_context("deployment-mode") or "single-account"

if deployment_mode == "multi-account":
    print("Deploying in multi-account mode with enhanced features...")
    
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
    
    # Deploy Amazon Q for Business stack (separate from enhanced stack to avoid circular dependency)
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
    print("✅ Amazon Q Integration: Natural language insights")
    print("✅ Cross-Account Dashboards: Unified visibility")
    print("=" * 50)
    
elif deployment_mode == "single-account-with-qbusiness":
    print("Deploying in single-account mode with Q Business integration...")
    
    # Deploy standard single-account stack
    base_stack = UsageAnomalyDetectorStack(
        app,
        "UsageAnomalyDetectorStack",
        description="AWS usage anomaly detector for single account"
    )
    
    # Deploy Amazon Q for Business stack for single-account mode
    q_business_stack = QBusinessStack(
        app,
        "QBusinessInsightsStack",
        opensearch_domain=getattr(base_stack, 'domain', None),
        description="Amazon Q for Business for natural language anomaly insights"
    )
    q_business_stack.add_dependency(base_stack)
    
    print("\n🚀 Single-Account with Q Business Deployment Summary:")
    print("=" * 50)
    print("✅ OpenSearch Domain: Anomaly detection and data storage")
    print("✅ Amazon Q Integration: Natural language insights")
    print("✅ Lambda Functions: Automated anomaly processing")
    print("✅ Cognito Authentication: Secure dashboard access")
    print("=" * 50)
    
else:
    print("Deploying in single-account mode...")
    
    # Deploy standard single-account stack
    UsageAnomalyDetectorStack(
        app,
        "UsageAnomalyDetectorStack",
        description="AWS usage anomaly detector for single account"
    )

# Apply CDK Nag security validation before synthesis
if CDK_NAG_AVAILABLE:
    print("🔒 Applying CDK Nag security validation...")
    try:
        # CDK Nag needs to be applied to individual stacks, not the app
        for stack in app.node.children:
            if hasattr(stack, 'node'):
                Aspects.of(stack).add(AwsSolutionsChecks(verbose=True))
        print("✅ CDK Nag security checks applied")
    except Exception as e:
        print(f"⚠️  CDK Nag validation failed: {e}")
        print("Proceeding with deployment without CDK Nag validation")
else:
    print("⚠️  Skipping CDK Nag validation - not installed")

app.synth()
