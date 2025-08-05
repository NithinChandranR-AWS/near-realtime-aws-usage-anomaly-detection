#!/usr/bin/env python3
"""
Comprehensive infrastructure validation for Enhanced Multi-Account Anomaly Detection System
"""

import boto3
import json
import time
import sys
from typing import Dict, List, Optional, Tuple
from botocore.exceptions import ClientError


class InfrastructureValidator:
    """Validates deployed infrastructure components"""
    
    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.cloudformation = boto3.client('cloudformation', region_name=region)
        self.cloudtrail = boto3.client('cloudtrail', region_name=region)
        self.opensearch = boto3.client('es', region_name=region)  # Using es client for compatibility
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.logs = boto3.client('logs', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.organizations = boto3.client('organizations', region_name=region)
        
    def validate_stack_deployment(self, stack_name: str) -> Tuple[bool, str]:
        """Validate that a CloudFormation stack is deployed successfully"""
        try:
            response = self.cloudformation.describe_stacks(StackName=stack_name)
            stack = response['Stacks'][0]
            status = stack['StackStatus']
            
            if status in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                return True, f"Stack {stack_name} is in {status} state"
            else:
                return False, f"Stack {stack_name} is in {status} state"
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                return False, f"Stack {stack_name} does not exist"
            else:
                return False, f"Error checking stack {stack_name}: {str(e)}"
    
    def validate_organization_trail(self) -> Tuple[bool, str]:
        """Validate organization-wide CloudTrail configuration"""
        try:
            trails = self.cloudtrail.describe_trails()['trailList']
            org_trails = [t for t in trails if t.get('IsOrganizationTrail', False)]
            
            if not org_trails:
                return False, "No organization trails found"
            
            # Check the first organization trail
            trail = org_trails[0]
            
            # Validate trail properties
            checks = [
                (trail.get('IsMultiRegionTrail', False), "Multi-region trail"),
                (trail.get('IncludeGlobalServiceEvents', False), "Global service events"),
                (trail.get('LogFileValidationEnabled', False), "Log file validation"),
                (trail.get('KmsKeyId') is not None, "KMS encryption"),
                (trail.get('CloudWatchLogsLogGroupArn') is not None, "CloudWatch Logs integration")
            ]
            
            failed_checks = [desc for check, desc in checks if not check]
            
            if failed_checks:
                return False, f"Trail validation failed: {', '.join(failed_checks)}"
            
            return True, f"Organization trail {trail['Name']} is properly configured"
            
        except ClientError as e:
            return False, f"Error validating organization trail: {str(e)}"
    
    def validate_opensearch_cluster(self, domain_name: str) -> Tuple[bool, str]:
        """Validate OpenSearch cluster health and configuration"""
        try:
            response = self.opensearch.describe_elasticsearch_domain(DomainName=domain_name)
            domain = response['DomainStatus']
            
            # Check domain status
            if not domain['Processing'] and domain['Created']:
                cluster_health = "healthy"
            else:
                cluster_health = "processing" if domain['Processing'] else "unhealthy"
            
            # Validate encryption
            encryption_at_rest = domain.get('EncryptionAtRestOptions', {}).get('Enabled', False)
            node_to_node_encryption = domain.get('NodeToNodeEncryptionOptions', {}).get('Enabled', False)
            domain_endpoint_options = domain.get('DomainEndpointOptions', {})
            enforce_https = domain_endpoint_options.get('EnforceHTTPS', False)
            
            security_checks = [
                (encryption_at_rest, "Encryption at rest"),
                (node_to_node_encryption, "Node-to-node encryption"),
                (enforce_https, "HTTPS enforcement")
            ]
            
            failed_security = [desc for check, desc in security_checks if not check]
            
            if failed_security:
                return False, f"OpenSearch security validation failed: {', '.join(failed_security)}"
            
            return True, f"OpenSearch domain {domain_name} is {cluster_health} and properly secured"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                return False, f"OpenSearch domain {domain_name} not found"
            else:
                return False, f"Error validating OpenSearch domain: {str(e)}"
    
    def validate_lambda_functions(self, function_names: List[str]) -> Tuple[bool, str]:
        """Validate Lambda functions are deployed and configured correctly"""
        results = []
        
        for function_name in function_names:
            try:
                response = self.lambda_client.get_function(FunctionName=function_name)
                config = response['Configuration']
                
                # Check function state
                state = config.get('State', 'Unknown')
                if state != 'Active':
                    results.append(f"{function_name}: State is {state}")
                    continue
                
                # Check runtime and timeout
                runtime = config.get('Runtime', '')
                timeout = config.get('Timeout', 0)
                
                if not runtime.startswith(('python3.', 'nodejs')):
                    results.append(f"{function_name}: Unexpected runtime {runtime}")
                
                if timeout < 60:
                    results.append(f"{function_name}: Timeout may be too low ({timeout}s)")
                
                results.append(f"{function_name}: Active and properly configured")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    results.append(f"{function_name}: Function not found")
                else:
                    results.append(f"{function_name}: Error - {str(e)}")
        
        failed_functions = [r for r in results if "Error" in r or "not found" in r or "State is" in r]
        
        if failed_functions:
            return False, f"Lambda validation failed: {'; '.join(failed_functions)}"
        
        return True, f"All Lambda functions validated: {'; '.join(results)}"
    
    def validate_cloudwatch_logs_integration(self, log_group_name: str) -> Tuple[bool, str]:
        """Validate CloudWatch Logs integration and subscription filters"""
        try:
            # Check log group exists
            response = self.logs.describe_log_groups(logGroupNamePrefix=log_group_name)
            log_groups = response['logGroups']
            
            if not log_groups:
                return False, f"Log group {log_group_name} not found"
            
            log_group = log_groups[0]
            
            # Check retention policy
            retention_days = log_group.get('retentionInDays')
            if not retention_days:
                return False, f"Log group {log_group_name} has no retention policy"
            
            # Check subscription filters
            filters_response = self.logs.describe_subscription_filters(
                logGroupName=log_group_name
            )
            subscription_filters = filters_response['subscriptionFilters']
            
            if not subscription_filters:
                return False, f"Log group {log_group_name} has no subscription filters"
            
            return True, f"Log group {log_group_name} is properly configured with {len(subscription_filters)} subscription filter(s)"
            
        except ClientError as e:
            return False, f"Error validating CloudWatch Logs: {str(e)}"
    
    def validate_organizations_access(self) -> Tuple[bool, str]:
        """Validate AWS Organizations access for account enumeration"""
        try:
            # Test organization access
            org_response = self.organizations.describe_organization()
            org_id = org_response['Organization']['Id']
            
            # Test account listing
            accounts_response = self.organizations.list_accounts(MaxResults=5)
            account_count = len(accounts_response['Accounts'])
            
            return True, f"Organizations access validated: Org {org_id}, {account_count} accounts accessible"
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AWSOrganizationsNotInUseException':
                return False, "AWS Organizations is not enabled for this account"
            elif error_code == 'AccessDeniedException':
                return False, "Access denied to AWS Organizations API"
            else:
                return False, f"Error accessing Organizations: {str(e)}"
    
    def run_comprehensive_validation(self, stack_names: List[str], 
                                   opensearch_domain: str,
                                   lambda_functions: List[str],
                                   log_group: str) -> Dict[str, Tuple[bool, str]]:
        """Run comprehensive validation of all infrastructure components"""
        
        print("🔍 Starting comprehensive infrastructure validation...")
        print("=" * 60)
        
        validations = {}
        
        # Validate CloudFormation stacks
        print("\n📋 Validating CloudFormation Stacks...")
        for stack_name in stack_names:
            validations[f"Stack: {stack_name}"] = self.validate_stack_deployment(stack_name)
        
        # Validate organization trail
        print("\n🛤️  Validating Organization Trail...")
        validations["Organization Trail"] = self.validate_organization_trail()
        
        # Validate OpenSearch cluster
        print("\n🔍 Validating OpenSearch Cluster...")
        validations["OpenSearch Cluster"] = self.validate_opensearch_cluster(opensearch_domain)
        
        # Validate Lambda functions
        print("\n⚡ Validating Lambda Functions...")
        validations["Lambda Functions"] = self.validate_lambda_functions(lambda_functions)
        
        # Validate CloudWatch Logs
        print("\n📊 Validating CloudWatch Logs Integration...")
        validations["CloudWatch Logs"] = self.validate_cloudwatch_logs_integration(log_group)
        
        # Validate Organizations access
        print("\n🏢 Validating Organizations Access...")
        validations["Organizations Access"] = self.validate_organizations_access()
        
        return validations
    
    def print_validation_results(self, validations: Dict[str, Tuple[bool, str]]) -> bool:
        """Print validation results and return overall success status"""
        
        print("\n" + "=" * 60)
        print("📊 VALIDATION RESULTS")
        print("=" * 60)
        
        passed = 0
        failed = 0
        
        for component, (success, message) in validations.items():
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {component}: {message}")
            
            if success:
                passed += 1
            else:
                failed += 1
        
        print("\n" + "=" * 60)
        print(f"📈 SUMMARY: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("🎉 All infrastructure components validated successfully!")
            return True
        else:
            print("⚠️  Some infrastructure components failed validation.")
            return False


def main():
    """Main validation function"""
    
    # Configuration - these would typically come from stack outputs
    STACK_NAMES = [
        "OrganizationTrailStack",
        "EnhancedAnomalyDetectorStack",
        "QBusinessStack",
        "MonitoringStack"
    ]
    
    # Get OpenSearch domain name dynamically from existing domains
    try:
        opensearch_client = boto3.client('es')
        domains = opensearch_client.list_domain_names()['DomainNames']
        OPENSEARCH_DOMAIN = next((d['DomainName'] for d in domains if 'anomaly' in d['DomainName'].lower()), None)
        if not OPENSEARCH_DOMAIN:
            print("⚠️  No anomaly detection OpenSearch domain found. Using placeholder.")
            OPENSEARCH_DOMAIN = "usage-anomaly-detector-domain"
    except Exception as e:
        print(f"⚠️  Could not detect OpenSearch domain: {e}")
        OPENSEARCH_DOMAIN = "usage-anomaly-detector-domain"
    
    LAMBDA_FUNCTIONS = [
        "MultiAccountLogsFunction",
        "CrossAccountConfigFunction", 
        "QBusinessConnectorFunction",
        "NLInsightsFunction",
        "SystemHealthMonitor"
    ]
    
    LOG_GROUP = "/aws/cloudtrail/organization"
    
    validator = InfrastructureValidator()
    
    try:
        validations = validator.run_comprehensive_validation(
            stack_names=STACK_NAMES,
            opensearch_domain=OPENSEARCH_DOMAIN,
            lambda_functions=LAMBDA_FUNCTIONS,
            log_group=LOG_GROUP
        )
        
        success = validator.print_validation_results(validations)
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Validation failed with error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()