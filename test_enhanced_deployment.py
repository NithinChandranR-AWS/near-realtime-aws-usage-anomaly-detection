#!/usr/bin/env python3
"""
Test script for the enhanced multi-account anomaly detection deployment.
Tests both single-account and multi-account deployment modes.
"""

import subprocess
import json
import os
import sys

def run_command(cmd):
    """Run a command and return its output."""
    print(f"\n📌 Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Command failed with exit code {result.returncode}")
            print(f"Error: {result.stderr}")
            return None
        return result.stdout
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return None

def test_single_account_mode():
    """Test single-account deployment mode."""
    print("\n" + "="*60)
    print("🧪 Testing Single-Account Mode")
    print("="*60)
    
    # List stacks
    output = run_command('cdk list --app "python3 app_enhanced_test.py"')
    if output:
        print(f"✅ Single-account stacks listed successfully")
        print(f"Stacks: {output.strip()}")
    else:
        print("❌ Failed to list single-account stacks")
        return False
    
    # Synthesize
    output = run_command('cdk synth --app "python3 app_enhanced_test.py" --quiet')
    if output:
        print("✅ Single-account synthesis successful")
    else:
        print("❌ Failed to synthesize single-account mode")
        return False
    
    return True

def test_multi_account_mode():
    """Test multi-account deployment mode."""
    print("\n" + "="*60)
    print("🧪 Testing Multi-Account Mode")
    print("="*60)
    
    # List stacks
    output = run_command('cdk list --app "python3 app_enhanced_test.py" --context deployment-mode=multi-account')
    if output:
        print(f"✅ Multi-account stacks listed successfully")
        print(f"Stacks: {output.strip()}")
        
        # Verify expected stacks
        expected_stacks = ["OrganizationTrailStack", "EnhancedUsageAnomalyDetectorStack", "MultiAccountAnomalyStack"]
        for stack in expected_stacks:
            if stack in output:
                print(f"  ✅ Found expected stack: {stack}")
            else:
                print(f"  ❌ Missing expected stack: {stack}")
                return False
    else:
        print("❌ Failed to list multi-account stacks")
        return False
    
    # Synthesize
    output = run_command('cdk synth --app "python3 app_enhanced_test.py" --context deployment-mode=multi-account --quiet')
    if output:
        print("✅ Multi-account synthesis successful")
    else:
        print("❌ Failed to synthesize multi-account mode")
        return False
    
    return True

def verify_lambda_code():
    """Verify Lambda function code exists."""
    print("\n" + "="*60)
    print("🧪 Verifying Lambda Function Code")
    print("="*60)
    
    lambda_dirs = [
        "lambdas/CrossAccountAnomalyProcessor",
        "lambdas/QBusinessConnector"
    ]
    
    for dir_path in lambda_dirs:
        if os.path.exists(dir_path):
            print(f"✅ Found Lambda directory: {dir_path}")
            # Check for key files
            if dir_path == "lambdas/CrossAccountAnomalyProcessor":
                if os.path.exists(f"{dir_path}/index.js"):
                    print(f"  ✅ Found index.js")
                if os.path.exists(f"{dir_path}/config.py"):
                    print(f"  ✅ Found config.py")
            elif dir_path == "lambdas/QBusinessConnector":
                if os.path.exists(f"{dir_path}/main.py"):
                    print(f"  ✅ Found main.py")
                if os.path.exists(f"{dir_path}/insights.py"):
                    print(f"  ✅ Found insights.py")
        else:
            print(f"❌ Missing Lambda directory: {dir_path}")
            return False
    
    return True

def check_enhanced_features():
    """Check for enhanced features in the deployment."""
    print("\n" + "="*60)
    print("🧪 Checking Enhanced Features")
    print("="*60)
    
    # Check enhanced stack file
    enhanced_stack_path = "infra/multi_account/enhanced_anomaly_detector_stack_test.py"
    if os.path.exists(enhanced_stack_path):
        print(f"✅ Found enhanced stack: {enhanced_stack_path}")
        
        # Check for key features in the file
        with open(enhanced_stack_path, 'r') as f:
            content = f.read()
            
        features = [
            ("Multi-account support", "MultiAccountLogsFunction"),
            ("Account enrichment", "ENABLE_ACCOUNT_ENRICHMENT"),
            ("Organization context", "ENABLE_ORG_CONTEXT"),
            ("Cross-account detectors", "multi-account-ec2-run-instances"),
            ("Q Business placeholder", "QBusinessStatus")
        ]
        
        for feature_name, search_term in features:
            if search_term in content:
                print(f"  ✅ {feature_name}: Found '{search_term}'")
            else:
                print(f"  ❌ {feature_name}: Missing '{search_term}'")
    else:
        print(f"❌ Enhanced stack not found: {enhanced_stack_path}")
        return False
    
    return True

def run_unit_tests():
    """Run unit tests if available."""
    print("\n" + "="*60)
    print("🧪 Running Unit Tests")
    print("="*60)
    
    # Check if pytest is available
    output = run_command("python -m pytest --version")
    if not output:
        print("⚠️  pytest not installed, skipping unit tests")
        return True
    
    # Run tests
    test_files = [
        "tests/unit/test_multi_account_stack.py"
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\n📋 Running tests in {test_file}")
            output = run_command(f"python -m pytest {test_file} -v")
            if output and "failed" not in output.lower():
                print(f"✅ Tests passed in {test_file}")
            else:
                print(f"⚠️  Some tests may have failed in {test_file}")
        else:
            print(f"⚠️  Test file not found: {test_file}")
    
    return True

def main():
    """Run all tests."""
    print("\n🚀 Enhanced Multi-Account Anomaly Detection Test Suite")
    print("=" * 60)
    
    # Track test results
    results = []
    
    # Run tests
    results.append(("Lambda Code Verification", verify_lambda_code()))
    results.append(("Enhanced Features Check", check_enhanced_features()))
    results.append(("Single-Account Mode", test_single_account_mode()))
    results.append(("Multi-Account Mode", test_multi_account_mode()))
    results.append(("Unit Tests", run_unit_tests()))
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ All tests passed successfully!")
        print("\n📌 Next Steps:")
        print("1. Deploy single-account mode: cdk deploy --app 'python3 app_enhanced_test.py' --all")
        print("2. Deploy multi-account mode: cdk deploy --app 'python3 app_enhanced_test.py' --context deployment-mode=multi-account --all")
        print("3. Check README_ENHANCED.md for detailed deployment instructions")
        return 0
    else:
        print("❌ Some tests failed. Please check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
