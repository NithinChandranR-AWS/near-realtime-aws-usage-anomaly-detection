#!/usr/bin/env python3
"""
Deployment validation script for Enhanced Multi-Account AWS Usage Anomaly Detection
"""

import boto3
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

# Colors for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_status(message: str):
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {message}")

def print_success(message: str):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {message}")

def print_warning(message: str):
    print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {message}")

def print_error(message: str):
    print(f"{Colors.RED}[ERROR]{Colors.NC} {message}")

class DeploymentValidator:
    def __init__(self, region: str = None):
        self.region = region or boto3.Session().region_name or 'us-east-1'
        self.session = boto3.Session()
        self.cloudformation = self.session.client('cloudformation', region_name=self.region)
        self.opensearch = self.session.client('opensearch', region_name=self.region)
        self.cloudtrail = self.session.client('cloudtrail', region_name=self.region)
        self.qbusiness = self.session.client('qbusiness', region_name=self.region)
        self.sns = self.session.client('sns', region_name=self.region)
        self.logs = self.session.client('logs', region_name=self.region)
        
        self.validation_results = {
            'stacks': {},
            'opensearch': {},
            'cloudtrail': {},
            'qbusiness': {},
            'lambda_functions': {},
            'overall_status': 'UNKNOWN'
        }

    def validate_all(self) -> Dict:
        """Run all validation checks"""
        print_status("Starting deployment validation...")
        print_status(f"Region: {self.region}")
        
        # Validate CloudFormation stacks
        self.validate_stacks()
        
        # Validate OpenSearch domain
        self.validate_opensearch()
        
        # Validate CloudTrail
        self.validate_cloudtrail()
        
        # Validate Q Business (if available)
        self.validate_qbusiness()
        
        # Validate Lambda functions
        self.validate_lambda_functions()
        
        # Generate overall status
        self.generate_overall_status()
        
        # Print summary
        self.print_summary()
        
        return self.validation_results

    def validate_stacks(self):
        """Validate CloudFormation stacks"""
        print_status("Validating CloudFormation stacks...")
        
        expected_stacks = [
            'OrganizationTrailStack',
            'EnhancedUsageAnomalyDetectorStack', 
            'MultiAccountAnomalyStack',
            'QBusinessInsightsStack'
        ]
        
        try:
            response = self.cloudformation.list_stacks(
                StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE']
            )
            
            existing_stacks = {stack['StackName']: stack['StackStatus'] 
                             for stack in response['StackSummaries']}
            
            for stack_name in expected_stacks:
                if stack_name in existing_stacks:
                    status = existing_stacks[stack_name]
                    self.validation_results['stacks'][stack_name] = {
                        'status': status,
                        'exists': True,
                        'healthy': status in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']
                    }
                    if status in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                        print_success(f"Stack {stack_name}: {status}")
                    else:
                        print_warning(f"Stack {stack_name}: {status}")
                else:
                    self.validation_results['stacks'][stack_name] = {
                        'status': 'NOT_FOUND',
                        'exists': False,
                        'healthy': False
                    }
                    print_error(f"Stack {stack_name}: NOT FOUND")
                    
        except Exception as e:
            print_error(f"Error validating stacks: {str(e)}")
            self.validation_results['stacks']['error'] = str(e)

    def validate_opensearch(self):
        """Validate OpenSearch domain"""
        print_status("Validating OpenSearch domain...")
        
        try:
            # Try to find the domain
            domains = self.opensearch.list_domain_names()
            anomaly_domains = [d for d in domains['DomainNames'] 
                             if 'usage-anomaly-detector' in d['DomainName']]
            
            if not anomaly_domains:
                print_error("OpenSearch domain not found")
                self.validation_results['opensearch'] = {
                    'exists': False,
                    'healthy': False,
                    'error': 'Domain not found'
                }
                return
            
            domain_name = anomaly_domains[0]['DomainName']
            domain_info = self.opensearch.describe_domain(DomainName=domain_name)
            domain = domain_info['DomainStatus']
            
            self.validation_results['opensearch'] = {
                'exists': True,
                'domain_name': domain_name,
                'processing': domain['Processing'],
                'endpoint': domain.get('Endpoint', 'Not available'),
                'version': domain['EngineVersion'],
                'healthy': not domain['Processing'] and domain.get('Endpoint') is not None
            }
            
            if domain['Processing']:
                print_warning(f"OpenSearch domain {domain_name} is still processing")
            elif domain.get('Endpoint'):
                print_success(f"OpenSearch domain {domain_name} is healthy")
                print_status(f"  Endpoint: {domain['Endpoint']}")
                print_status(f"  Version: {domain['EngineVersion']}")
            else:
                print_error(f"OpenSearch domain {domain_name} has no endpoint")
                
        except Exception as e:
            print_error(f"Error validating OpenSearch: {str(e)}")
            self.validation_results['opensearch'] = {
                'exists': False,
                'healthy': False,
                'error': str(e)
            }

    def validate_cloudtrail(self):
        """Validate CloudTrail configuration"""
        print_status("Validating CloudTrail...")
        
        try:
            trails = self.cloudtrail.describe_trails()
            org_trails = [t for t in trails['trailList'] 
                         if 'org-trail' in t['Name'] or t.get('IsOrganizationTrail', False)]
            
            if not org_trails:
                print_warning("No organization trail found")
                self.validation_results['cloudtrail'] = {
                    'exists': False,
                    'healthy': False,
                    'error': 'No organization trail found'
                }
                return
            
            trail = org_trails[0]
            trail_status = self.cloudtrail.get_trail_status(Name=trail['TrailARN'])
            
            self.validation_results['cloudtrail'] = {
                'exists': True,
                'name': trail['Name'],
                'is_logging': trail_status['IsLogging'],
                'is_organization_trail': trail.get('IsOrganizationTrail', False),
                'is_multi_region': trail.get('IsMultiRegionTrail', False),
                'has_log_file_validation': trail.get('LogFileValidationEnabled', False),
                'healthy': trail_status['IsLogging']
            }
            
            if trail_status['IsLogging']:
                print_success(f"CloudTrail {trail['Name']} is logging")
                if trail.get('IsOrganizationTrail'):
                    print_success("  Organization-wide trail configured")
                if trail.get('IsMultiRegionTrail'):
                    print_success("  Multi-region trail enabled")
            else:
                print_error(f"CloudTrail {trail['Name']} is not logging")
                
        except Exception as e:
            print_error(f"Error validating CloudTrail: {str(e)}")
            self.validation_results['cloudtrail'] = {
                'exists': False,
                'healthy': False,
                'error': str(e)
            }

    def validate_qbusiness(self):
        """Validate Q Business configuration"""
        print_status("Validating Q Business...")
        
        try:
            applications = self.qbusiness.list_applications()
            anomaly_apps = [app for app in applications.get('applications', [])
                           if 'anomaly' in app.get('displayName', '').lower()]
            
            if not anomaly_apps:
                print_warning("Q Business application not found")
                self.validation_results['qbusiness'] = {
                    'exists': False,
                    'healthy': False,
                    'error': 'Application not found'
                }
                return
            
            app = anomaly_apps[0]
            app_details = self.qbusiness.get_application(applicationId=app['applicationId'])
            
            self.validation_results['qbusiness'] = {
                'exists': True,
                'application_id': app['applicationId'],
                'display_name': app.get('displayName'),
                'status': app.get('status'),
                'identity_type': app_details.get('identityType'),
                'healthy': app.get('status') == 'ACTIVE'
            }
            
            if app.get('status') == 'ACTIVE':
                print_success(f"Q Business application {app.get('displayName')} is active")
            else:
                print_warning(f"Q Business application status: {app.get('status')}")
                
        except Exception as e:
            print_warning(f"Q Business validation skipped: {str(e)}")
            self.validation_results['qbusiness'] = {
                'exists': False,
                'healthy': False,
                'error': f'Service not available: {str(e)}'
            }

    def validate_lambda_functions(self):
        """Validate Lambda functions"""
        print_status("Validating Lambda functions...")
        
        lambda_client = self.session.client('lambda', region_name=self.region)
        
        expected_functions = [
            'MultiAccountLogsFunction',
            'CrossAccountConfigFunction', 
            'QBusinessConnectorFunction',
            'NaturalLanguageInsightsFunction'
        ]
        
        try:
            functions = lambda_client.list_functions()
            existing_functions = {f['FunctionName']: f for f in functions['Functions']}
            
            for func_name in expected_functions:
                matching_funcs = [name for name in existing_functions.keys() 
                                if func_name.lower() in name.lower()]
                
                if matching_funcs:
                    actual_name = matching_funcs[0]
                    func_info = existing_functions[actual_name]
                    
                    self.validation_results['lambda_functions'][func_name] = {
                        'exists': True,
                        'actual_name': actual_name,
                        'runtime': func_info['Runtime'],
                        'last_modified': func_info['LastModified'],
                        'healthy': True
                    }
                    print_success(f"Lambda function {actual_name} found")
                else:
                    self.validation_results['lambda_functions'][func_name] = {
                        'exists': False,
                        'healthy': False,
                        'error': 'Function not found'
                    }
                    print_error(f"Lambda function {func_name} not found")
                    
        except Exception as e:
            print_error(f"Error validating Lambda functions: {str(e)}")
            self.validation_results['lambda_functions']['error'] = str(e)

    def generate_overall_status(self):
        """Generate overall deployment status"""
        issues = []
        
        # Check stacks
        for stack_name, stack_info in self.validation_results['stacks'].items():
            if stack_name != 'error' and not stack_info.get('healthy', False):
                issues.append(f"Stack {stack_name} is not healthy")
        
        # Check OpenSearch
        if not self.validation_results['opensearch'].get('healthy', False):
            issues.append("OpenSearch domain is not healthy")
        
        # Check CloudTrail
        if not self.validation_results['cloudtrail'].get('healthy', False):
            issues.append("CloudTrail is not healthy")
        
        # Check Lambda functions
        for func_name, func_info in self.validation_results['lambda_functions'].items():
            if func_name != 'error' and not func_info.get('healthy', False):
                issues.append(f"Lambda function {func_name} is not healthy")
        
        if not issues:
            self.validation_results['overall_status'] = 'HEALTHY'
        elif len(issues) <= 2:
            self.validation_results['overall_status'] = 'DEGRADED'
        else:
            self.validation_results['overall_status'] = 'UNHEALTHY'
        
        self.validation_results['issues'] = issues

    def print_summary(self):
        """Print validation summary"""
        print("\n" + "="*60)
        print("DEPLOYMENT VALIDATION SUMMARY")
        print("="*60)
        
        status = self.validation_results['overall_status']
        if status == 'HEALTHY':
            print_success(f"Overall Status: {status}")
            print_success("✅ All components are healthy and operational")
        elif status == 'DEGRADED':
            print_warning(f"Overall Status: {status}")
            print_warning("⚠️  Some components have issues but core functionality works")
        else:
            print_error(f"Overall Status: {status}")
            print_error("❌ Multiple components have issues")
        
        if self.validation_results.get('issues'):
            print("\nIssues found:")
            for issue in self.validation_results['issues']:
                print_error(f"  - {issue}")
        
        print("\nComponent Status:")
        
        # Stacks
        stack_count = len([s for s in self.validation_results['stacks'].values() 
                          if isinstance(s, dict) and s.get('healthy')])
        total_stacks = len([s for s in self.validation_results['stacks'].keys() 
                          if s != 'error'])
        print(f"  📦 CloudFormation Stacks: {stack_count}/{total_stacks} healthy")
        
        # OpenSearch
        os_status = "✅" if self.validation_results['opensearch'].get('healthy') else "❌"
        print(f"  🔍 OpenSearch Domain: {os_status}")
        
        # CloudTrail
        ct_status = "✅" if self.validation_results['cloudtrail'].get('healthy') else "❌"
        print(f"  📋 CloudTrail: {ct_status}")
        
        # Q Business
        qb_status = "✅" if self.validation_results['qbusiness'].get('healthy') else "⚠️"
        print(f"  🤖 Q Business: {qb_status}")
        
        # Lambda functions
        lambda_count = len([f for f in self.validation_results['lambda_functions'].values() 
                           if isinstance(f, dict) and f.get('healthy')])
        total_lambdas = len([f for f in self.validation_results['lambda_functions'].keys() 
                           if f != 'error'])
        print(f"  ⚡ Lambda Functions: {lambda_count}/{total_lambdas} healthy")
        
        print("\n" + "="*60)
        
        if status == 'HEALTHY':
            print_success("🎉 Deployment validation completed successfully!")
            print_status("Your enhanced multi-account anomaly detection system is ready to use.")
        else:
            print_warning("⚠️  Deployment validation completed with issues.")
            print_status("Please review the issues above and take corrective action.")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Validate Enhanced Multi-Account AWS Usage Anomaly Detection deployment'
    )
    parser.add_argument(
        '-r', '--region',
        help='AWS region to validate (default: current session region)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format'
    )
    
    args = parser.parse_args()
    
    try:
        validator = DeploymentValidator(region=args.region)
        results = validator.validate_all()
        
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        
        # Exit with appropriate code
        status = results['overall_status']
        if status == 'HEALTHY':
            sys.exit(0)
        elif status == 'DEGRADED':
            sys.exit(1)
        else:
            sys.exit(2)
            
    except Exception as e:
        print_error(f"Validation failed: {str(e)}")
        sys.exit(3)

if __name__ == '__main__':
    main()