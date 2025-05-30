"""
Utility to check Q Business availability in current CDK version.
"""

def is_q_business_available():
    """Check if aws_qbusiness module is available."""
    try:
        from aws_cdk import aws_qbusiness
        # Check for required classes
        required = ['CfnApplication', 'CfnIndex', 'CfnDataSource', 'CfnRetriever', 'CfnWebExperience']
        return all(hasattr(aws_qbusiness, cls) for cls in required)
    except ImportError:
        return False

def get_q_business_status():
    """Get Q Business availability status message."""
    if is_q_business_available():
        return "✅ Q Business Integration: Enabled - Natural language insights active"
    else:
        return "⚠️  Q Business Integration: Disabled (requires CDK v2.110.0+, current: v2.103.1)"
