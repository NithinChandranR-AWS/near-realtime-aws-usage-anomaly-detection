#!/usr/bin/env python3
import os
import aws_cdk as cdk
from infra.usage_anomaly_detector import UsageAnomalyDetectorStack
from infra.multi_account.organization_trail_stack import OrganizationTrailStack
from infra.multi_account.enhanced_anomaly_detector_stack import EnhancedAnomalyDetectorStack
from infra.multi_account.q_business_stack import QBusinessStack

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
        opensearch_domain=base_stack.domain if hasattr(base_stack, 'domain') else None,
        description="Multi-account anomaly detection with natural language insights"
    )
    enhanced_stack.add_dependency(org_trail_stack)
    enhanced_stack.add_dependency(base_stack)
    
    # Deploy Amazon Q for Business stack
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
    
else:
    print("Deploying in single-account mode...")
    
    # Deploy standard single-account stack
    UsageAnomalyDetectorStack(
        app,
        "UsageAnomalyDetectorStack",
        description="AWS usage anomaly detector for single account"
    )

app.synth()
