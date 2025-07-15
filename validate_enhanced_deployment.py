#!/usr/bin/env python3
"""
Enhanced Multi-Account Anomaly Detection Deployment Validator

This script validates that all components of the multi-account anomaly detection
system are properly deployed and functioning.
"""

import boto3
import json
import sys
import time
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

class DeploymentValidator:
    def __init__(self):
        self.cloudformation = boto3.client('cloudformation')
        self.lambda_client = boto3.client('lambda')
        self.opensearch = boto3.client('opensearch')
        self.cloudwatch = boto3.client('cloudwatch')
        self.sns = boto3.client('sns')
        self.logs = boto3.client('logs')
        
        self.validation_results = {
            'stacks': {},
            'lambda_functions': {},
            'opensearch': {},
            'monitoring': {},
            'overall_status': 'UNKNOWN'
        }
    
    def validate_deployment(self):
        """Run complete deployment validation"""
        print("🔍 Starting Enhanced Multi-Account Anomaly Detection Validation")
        print("=" * 70)
        
        try:
            # Validate CloudFormation stacks
            self.validate_stacks()
            
            # Validate Lambda functions
            self.validate_lambda_functions()
            
            # Validate OpenSearch domain
            self.validate_opensearch()
            
            # Validate monitoring components
            self.validate_monitoring()
            
            # Generate final report
            self.generate_report()
            
        except Exception as e:
            print(f"❌ Validation failed with error: {str(e)}")
            self.validation_results['overall_status'] = 'FAILED'
            return False
        
        return self.validation_results['overall_status'] == 'HEALTHY'
    
    def validate_stacks(self):
        """Validate CloudFormation stacks"""
        print("\n📋 Validating CloudFormation Stacks...")
        
        expected_stacks = [
            'OrganizationTrailStack',
            'EnhancedUsageAnomalyDetectorStack',
            'MultiAccountAnomalyStack'
        ]
        
        for stack_name in expected_stacks:
            try:
                response = self.cloudformation.describe_stacks(StackName=stack_name)
                stack = response['Stacks'][0]
                status = stack['StackStatus']
                
                if status in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                    print(f"  ✅ {stack_name}: {status}")
                    self.validation_results['stacks'][stack_name] = {
                        'status': 'HEALTHY',
                        'stack_status': status,
                        'creation_time': stack['CreationTime'].isoformat()
                    }
                else:
                    print(f"  ⚠️  {stack_name}: {status}")
                    self.validation_results['stacks'][stack_name] = {
                        'status': 'WARNING',
                        'stack_status': status
                    }
                    
            except ClientError as e:
                if e.response['Error']['Code'] == 'ValidationError':
                    print(f"  ❌ {stack_name}: NOT FOUND")
                    self.validation_results['stacks'][stack_name] = {
                        'status': 'MISSING',
                        'error': 'Stack not found'
                    }
                else:
                    print(f"  ❌ {stack_name}: ERROR - {str(e)}")
                    self.validation_results['stacks'][stack_name] = {
                        'status': 'ERROR',
                        'error': str(e)
                    }
    
    def validate_lambda_functions(self):
        """Validate Lambda functions"""
        print("\n🔧 Validating Lambda Functions...")
        
        # Get function names from stack outputs
        function_names = self.get_lambda_function_names()
        
        for function_name in function_names:
            try:
                # Get function configuration
                response = self.lambda_client.get_function(FunctionName=function_name)
                config = response['Configuration']
                
                # Check function state
                state = config.get('State', 'Unknown')
                last_update_status = config.get('LastUpdateStatus', 'Unknown')
                
                if state == 'Active' and last_update_status == 'Successful':
                    print(f"  ✅ {function_name}: Active and ready")
                    
                    # Test function invocation
                    test_result = self.test_lambda_function(function_name)
                    
                    self.validation_results['lambda_functions'][function_name] = {
                        'status': 'HEALTHY',
                        'state': state,
                        'runtime': config.get('Runtime', 'Unknown'),
                        'last_modified': config.get('LastModified', 'Unknown'),
                        'test_result': test_result
                    }
                else:
                    print(f"  ⚠️  {function_name}: {state} - {last_update_status}")
                    self.validation_results['lambda_functions'][function_name] = {
                        'status': 'WARNING',
                        'state': state,
                        'last_update_status': last_update_status
                    }
                    
            except ClientError as e:
                print(f"  ❌ {function_name}: ERROR - {str(e)}")
                self.validation_results['lambda_functions'][function_name] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
    
    def get_lambda_function_names(self):
        """Get Lambda function names from stack outputs"""
        function_names = []
        
        try:
            # Get function names from MultiAccountAnomalyStack outputs
            response = self.cloudformation.describe_stacks(
                StackName='MultiAccountAnomalyStack'
            )
            
            outputs = response['Stacks'][0].get('Outputs', [])
            
            for output in outputs:
                if 'FunctionArn' in output['OutputKey']:
                    # Extract function name from ARN
                    arn = output['OutputValue']
                    function_name = arn.split(':')[-1]
                    function_names.append(function_name)
                    
        except Exception as e:
            print(f"  ⚠️  Could not get function names from stack outputs: {str(e)}")
            
            # Fallback: try common function names
            common_names = [
                'MultiAccountAnomalyStack-MultiAccountLogsFunction',
                'MultiAccountAnomalyStack-QBusinessConnectorFunction',
                'MultiAccountAnomalyStack-SystemHealthMonitorFunction'
            ]
            
            for name in common_names:
                try:
                    self.lambda_client.get_function(FunctionName=name)
                    function_names.append(name)
                except:
                    pass
        
        return function_names
    
    def test_lambda_function(self, function_name):
        """Test Lambda function with a simple invocation"""
        try:
            # Create a test event
            test_event = {
                'test': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Invoke function asynchronously to avoid timeout
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='Event',  # Async invocation
                Payload=json.dumps(test_event)
            )
            
            if response['StatusCode'] == 202:
                return {'status': 'SUCCESS', 'message': 'Function invoked successfully'}
            else:
                return {'status': 'WARNING', 'message': f'Unexpected status code: {response["StatusCode"]}'}
                
        except Exception as e:
            return {'status': 'ERROR', 'message': str(e)}
    
    def validate_opensearch(self):
        """Validate OpenSearch domain"""
        print("\n🔍 Validating OpenSearch Domain...")
        
        try:
            # List domains to find the anomaly detection domain
            response = self.opensearch.list_domain_names()
            domain_names = [domain['DomainName'] for domain in response['DomainNames']]
            
            # Look for anomaly detection domain
            anomaly_domain = None
            for domain_name in domain_names:
                if 'anomaly' in domain_name.lower() or 'usage' in domain_name.lower():
                    anomaly_domain = domain_name
                    break
            
            if not anomaly_domain:
                print("  ❌ OpenSearch domain not found")
                self.validation_results['opensearch'] = {
                    'status': 'MISSING',
                    'error': 'No anomaly detection domain found'
                }
                return
            
            # Get domain status
            response = self.opensearch.describe_domain(DomainName=anomaly_domain)
            domain = response['DomainStatus']
            
            processing = domain.get('Processing', False)
            created = domain.get('Created', False)
            deleted = domain.get('Deleted', False)
            
            if created and not processing and not deleted:
                print(f"  ✅ {anomaly_domain}: Active and ready")
                self.validation_results['opensearch'] = {
                    'status': 'HEALTHY',
                    'domain_name': anomaly_domain,
                    'endpoint': domain.get('Endpoint', 'Unknown'),
                    'elasticsearch_version': domain.get('ElasticsearchVersion', 'Unknown'),
                    'instance_type': domain.get('ElasticsearchClusterConfig', {}).get('InstanceType', 'Unknown')
                }
            else:
                print(f"  ⚠️  {anomaly_domain}: Processing={processing}, Created={created}, Deleted={deleted}")
                self.validation_results['opensearch'] = {
                    'status': 'WARNING',
                    'domain_name': anomaly_domain,
                    'processing': processing,
                    'created': created,
                    'deleted': deleted
                }
                
        except Exception as e:
            print(f"  ❌ OpenSearch validation failed: {str(e)}")
            self.validation_results['opensearch'] = {
                'status': 'ERROR',
                'error': str(e)
            }
    
    def validate_monitoring(self):
        """Validate monitoring components"""
        print("\n📊 Validating Monitoring Components...")
        
        # Check CloudWatch dashboard
        try:
            response = self.cloudwatch.list_dashboards()
            dashboards = response.get('DashboardEntries', [])
            
            anomaly_dashboard = None
            for dashboard in dashboards:
                if 'anomaly' in dashboard['DashboardName'].lower():
                    anomaly_dashboard = dashboard
                    break
            
            if anomaly_dashboard:
                print(f"  ✅ Dashboard: {anomaly_dashboard['DashboardName']}")
                self.validation_results['monitoring']['dashboard'] = {
                    'status': 'HEALTHY',
                    'name': anomaly_dashboard['DashboardName']
                }
            else:
                print("  ⚠️  No anomaly detection dashboard found")
                self.validation_results['monitoring']['dashboard'] = {
                    'status': 'WARNING',
                    'message': 'Dashboard not found'
                }
                
        except Exception as e:
            print(f"  ❌ Dashboard validation failed: {str(e)}")
            self.validation_results['monitoring']['dashboard'] = {
                'status': 'ERROR',
                'error': str(e)
            }
        
        # Check SNS topics
        try:
            response = self.sns.list_topics()
            topics = response.get('Topics', [])
            
            alert_topics = [topic for topic in topics if 'alert' in topic['TopicArn'].lower()]
            
            if alert_topics:
                print(f"  ✅ Alert Topics: {len(alert_topics)} found")
                self.validation_results['monitoring']['sns_topics'] = {
                    'status': 'HEALTHY',
                    'count': len(alert_topics)
                }
            else:
                print("  ⚠️  No alert topics found")
                self.validation_results['monitoring']['sns_topics'] = {
                    'status': 'WARNING',
                    'message': 'No alert topics found'
                }
                
        except Exception as e:
            print(f"  ❌ SNS validation failed: {str(e)}")
            self.validation_results['monitoring']['sns_topics'] = {
                'status': 'ERROR',
                'error': str(e)
            }
        
        # Check custom metrics
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)
            
            response = self.cloudwatch.list_metrics(
                Namespace='MultiAccountAnomalyDetection'
            )
            
            custom_metrics = response.get('Metrics', [])
            
            if custom_metrics:
                print(f"  ✅ Custom Metrics: {len(custom_metrics)} metrics found")
                self.validation_results['monitoring']['custom_metrics'] = {
                    'status': 'HEALTHY',
                    'count': len(custom_metrics)
                }
            else:
                print("  ⚠️  No custom metrics found (may take time to appear)")
                self.validation_results['monitoring']['custom_metrics'] = {
                    'status': 'WARNING',
                    'message': 'No custom metrics found yet'
                }
                
        except Exception as e:
            print(f"  ❌ Custom metrics validation failed: {str(e)}")
            self.validation_results['monitoring']['custom_metrics'] = {
                'status': 'ERROR',
                'error': str(e)
            }
    
    def generate_report(self):
        """Generate final validation report"""
        print("\n📋 Validation Report")
        print("=" * 50)
        
        # Count status types
        total_components = 0
        healthy_components = 0
        warning_components = 0
        error_components = 0
        
        # Analyze results
        for category, components in self.validation_results.items():
            if category == 'overall_status':
                continue
                
            if isinstance(components, dict):
                for component, status in components.items():
                    total_components += 1
                    
                    if isinstance(status, dict):
                        component_status = status.get('status', 'UNKNOWN')
                    else:
                        component_status = status
                    
                    if component_status == 'HEALTHY':
                        healthy_components += 1
                    elif component_status in ['WARNING', 'MISSING']:
                        warning_components += 1
                    else:
                        error_components += 1
        
        # Determine overall status
        if error_components > 0:
            overall_status = 'UNHEALTHY'
            status_emoji = '❌'
        elif warning_components > 0:
            overall_status = 'DEGRADED'
            status_emoji = '⚠️'
        else:
            overall_status = 'HEALTHY'
            status_emoji = '✅'
        
        self.validation_results['overall_status'] = overall_status
        
        # Print summary
        print(f"Overall Status: {status_emoji} {overall_status}")
        print(f"Total Components: {total_components}")
        print(f"Healthy: {healthy_components}")
        print(f"Warnings: {warning_components}")
        print(f"Errors: {error_components}")
        
        # Print recommendations
        print("\n💡 Recommendations:")
        if error_components > 0:
            print("  • Check CloudFormation stack events for deployment errors")
            print("  • Review Lambda function logs for runtime errors")
            print("  • Verify IAM permissions and resource dependencies")
        elif warning_components > 0:
            print("  • Monitor system for a few minutes to allow initialization")
            print("  • Check that all required AWS services are available in your region")
        else:
            print("  • System is healthy and ready for use!")
            print("  • Consider setting up SNS subscriptions for alerts")
            print("  • Review CloudWatch dashboards for system metrics")
        
        # Save detailed results
        with open('validation_results.json', 'w') as f:
            json.dump(self.validation_results, f, indent=2, default=str)
        
        print(f"\n📄 Detailed results saved to: validation_results.json")
        print("=" * 50)

def main():
    """Main validation function"""
    validator = DeploymentValidator()
    
    try:
        success = validator.validate_deployment()
        
        if success:
            print("\n🎉 Validation completed successfully!")
            sys.exit(0)
        else:
            print("\n⚠️  Validation completed with issues.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Validation interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Validation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()