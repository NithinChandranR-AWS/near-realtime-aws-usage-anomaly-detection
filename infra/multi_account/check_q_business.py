"""
Utility to check Q Business availability in current CDK version.
"""

def get_cdk_version():
    """Get the current CDK version."""
    try:
        import aws_cdk_lib
        return getattr(aws_cdk_lib, '__version__', 'unknown')
    except ImportError:
        try:
            import aws_cdk
            return getattr(aws_cdk, '__version__', 'unknown')
        except ImportError:
            return 'unknown'

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
    current_version = get_cdk_version()
    if is_q_business_available():
        return f"✅ Q Business Integration: Enabled - Natural language insights active (CDK v{current_version})"
    else:
        return f"⚠️  Q Business Integration: Disabled (requires CDK v2.110.0+, current: v{current_version})"
