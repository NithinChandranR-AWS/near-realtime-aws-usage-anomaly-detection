import json
import os
import boto3  # type: ignore
import requests
from requests.auth import HTTPBasicAuth
import time
import traceback
from datetime import datetime

# Environment variables
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST')
ENABLE_MULTI_ACCOUNT = os.environ.get('ENABLE_MULTI_ACCOUNT', 'true').lower() == 'true'
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Initialize AWS clients
organizations = boto3.client('organizations')


def handler(event, context):
    """
    Lambda handler to configure multi-account anomaly detectors
    """
    start_time = datetime.utcnow()
    print(f"Starting multi-account detector configuration at {start_time}")
    print(f"Event: {json.dumps(event, default=str)}")
    
    request_type = event.get('RequestType', 'Create')
    
    try:
        if request_type in ['Create', 'Update']:
            # Get organization accounts
            print("Fetching organization accounts...")
            accounts = get_organization_accounts()
            print(f"Found {len(accounts)} accounts in organization")
            
            # Log account details
            for account in accounts[:5]:  # Log first 5 accounts
                print(f"  - Account: {account['name']} ({account['id']})")
            if len(accounts) > 5:
                print(f"  - ... and {len(accounts) - 5} more accounts")
            
            # Create multi-account anomaly detectors
            detectors = event['ResourceProperties'].get('detectors', [])
            print(f"Creating {len(detectors)} anomaly detectors...")
            results = []
            
            for detector_config in detectors:
                print(f"Creating detector: {detector_config['name']}")
                result = create_multi_account_detector(detector_config, accounts)
                results.append(result)
                print(f"  - Status: {result['status']}")
            
            # Create cross-account dashboards
            print("Creating cross-account dashboards...")
            create_cross_account_dashboards()
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            print(f"Configuration completed in {processing_time:.2f} seconds")
            
            return {
                'PhysicalResourceId': f'multi-account-detectors-{context.request_id}',
                'Data': {
                    'DetectorsCreated': len(results),
                    'AccountsMonitored': len(accounts),
                    'ProcessingTimeSeconds': processing_time,
                    'ConfigurationStatus': 'SUCCESS'
                }
            }
            
        elif request_type == 'Delete':
            # Clean up detectors if needed
            print("Delete request - performing cleanup...")
            cleanup_detectors()
            return {
                'PhysicalResourceId': event.get('PhysicalResourceId', 'deleted'),
                'Data': {
                    'ConfigurationStatus': 'DELETED'
                }
            }
            
    except Exception as e:
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        print(f"Error after {processing_time:.2f} seconds: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        
        # Return failure response for CloudFormation
        return {
            'PhysicalResourceId': event.get('PhysicalResourceId', f'failed-{context.request_id}'),
            'Data': {
                'ConfigurationStatus': 'FAILED',
                'ErrorMessage': str(e),
                'ProcessingTimeSeconds': processing_time
            }
        }


def get_organization_accounts():
    """
    Get all accounts in the AWS Organization
    """
    accounts = []
    paginator = organizations.get_paginator('list_accounts')
    
    for page in paginator.paginate():
        for account in page['Accounts']:
            if account['Status'] == 'ACTIVE':
                accounts.append({
                    'id': account['Id'],
                    'name': account['Name'],
                    'email': account['Email']
                })
    
    return accounts


def create_multi_account_detector(detector_config, accounts):
    """
    Create a multi-account anomaly detector with account-based categories
    """
    detector_name = detector_config['name']
    category_fields = detector_config.get('category_fields', [])
    
    # Base detector configuration
    detector_body = {
        "name": detector_name,
        "description": f"Multi-account anomaly detector for {detector_name}",
        "time_field": "eventTime",
        "indices": ["cwl-multiaccounts*"],
        "detection_interval": {
            "period": {
                "interval": 10,
                "unit": "Minutes"
            }
        },
        "window_delay": {
            "period": {
                "interval": 5,
                "unit": "Minutes"
            }
        },
        "shingle_size": 8,
        "category_field": category_fields
    }
    
    # Add feature based on detector type
    if 'ec2' in detector_name:
        detector_body['feature_attributes'] = [{
            "feature_name": "ec2_instances",
            "feature_enabled": True,
            "aggregation_query": {
                "instances_count": {
                    "sum": {
                        "field": "requestParameters.instancesSet.items.maxCount"
                    }
                }
            }
        }]
        detector_body['filter_query'] = {
            "bool": {
                "filter": [{
                    "term": {
                        "eventName.keyword": "RunInstances"
                    }
                }]
            }
        }
    elif 'lambda' in detector_name:
        detector_body['feature_attributes'] = [{
            "feature_name": "lambda_invocations",
            "feature_enabled": True,
            "aggregation_query": {
                "invocation_count": {
                    "value_count": {
                        "field": "eventName.keyword"
                    }
                }
            }
        }]
        detector_body['filter_query'] = {
            "bool": {
                "filter": [{
                    "term": {
                        "eventName.keyword": "Invoke"
                    }
                }]
            }
        }
    elif 'ebs' in detector_name:
        detector_body['feature_attributes'] = [{
            "feature_name": "volume_creations",
            "feature_enabled": True,
            "aggregation_query": {
                "volume_count": {
                    "value_count": {
                        "field": "eventName.keyword"
                    }
                }
            }
        }]
        detector_body['filter_query'] = {
            "bool": {
                "filter": [{
                    "term": {
                        "eventName.keyword": "CreateVolume"
                    }
                }]
            }
        }
    
    # Create the detector
    response = opensearch_request(
        'POST',
        '/_plugins/_anomaly_detection/detectors',
        detector_body
    )
    
    detector_id = response.get('_id')
    print(f"Created detector {detector_name} with ID: {detector_id}")
    
    # Start the detector
    start_response = opensearch_request(
        'POST',
        f'/_plugins/_anomaly_detection/detectors/{detector_id}/_start'
    )
    
    print(f"Started detector {detector_name}")
    
    # Create monitor for the detector
    create_detector_monitor(detector_name, detector_id)
    
    return {
        'name': detector_name,
        'id': detector_id,
        'status': 'started'
    }


def create_detector_monitor(detector_name, detector_id):
    """
    Create an alerting monitor for the anomaly detector
    """
    monitor_body = {
        "name": f"{detector_name}-monitor",
        "type": "monitor",
        "enabled": True,
        "schedule": {
            "period": {
                "interval": 5,
                "unit": "MINUTES"
            }
        },
        "inputs": [{
            "search": {
                "indices": [f".opendistro-anomaly-results-{detector_id}*"],
                "query": {
                    "bool": {
                        "filter": [{
                            "range": {
                                "anomaly_grade": {
                                    "gt": 0.7
                                }
                            }
                        }]
                    }
                }
            }
        }],
        "triggers": [{
            "name": f"{detector_name}-trigger",
            "severity": "1",
            "condition": {
                "script": {
                    "source": "ctx.results[0].hits.total.value > 0",
                    "lang": "painless"
                }
            },
            "actions": [{
                "name": f"{detector_name}-action",
                "destination_id": create_sns_destination(),
                "message_template": {
                    "source": json.dumps({
                        "Alert": f"Multi-account anomaly detected in {detector_name}",
                        "Detector": detector_name,
                        "Time": "{{ctx.periodStart}}",
                        "Anomalies": "{{ctx.results[0].hits.total.value}}",
                        "TopAccounts": "{{#ctx.results[0].hits.hits}}{{_source.entity}}{{/ctx.results[0].hits.hits}}"
                    })
                }
            }]
        }]
    }
    
    response = opensearch_request(
        'POST',
        '/_plugins/_alerting/monitors',
        monitor_body
    )
    
    print(f"Created monitor for {detector_name}")
    return response


def create_sns_destination():
    """
    Create or get SNS destination for alerts
    """
    # Check if destination already exists
    destinations = opensearch_request(
        'GET',
        '/_plugins/_alerting/destinations'
    )
    
    for dest in destinations.get('destinations', []):
        if dest['name'] == 'multi-account-sns-destination':
            return dest['id']
    
    # Create new destination
    sns_topic_arn = os.environ.get('SNS_TOPIC_ARN')
    sns_role_arn = os.environ.get('SNS_ALERT_ROLE')
    
    destination_body = {
        "name": "multi-account-sns-destination",
        "type": "sns",
        "sns": {
            "topic_arn": sns_topic_arn,
            "role_arn": sns_role_arn
        }
    }
    
    response = opensearch_request(
        'POST',
        '/_plugins/_alerting/destinations',
        destination_body
    )
    
    return response['_id']


def create_cross_account_dashboards():
    """
    Create OpenSearch dashboards for cross-account visualization
    """
    # Create index pattern for multi-account data
    index_pattern = {
        "attributes": {
            "title": "cwl-multiaccounts*",
            "timeFieldName": "eventTime",
            "fields": json.dumps([
                {"name": "recipientAccountId", "type": "string"},
                {"name": "accountAlias", "type": "string"},
                {"name": "accountType", "type": "string"},
                {"name": "eventName", "type": "string"},
                {"name": "awsRegion", "type": "string"},
                {"name": "eventTime", "type": "date"}
            ])
        }
    }
    
    # Create dashboard configurations
    dashboards = [
        {
            "id": "multi-account-overview",
            "attributes": {
                "title": "Multi-Account Anomaly Overview",
                "hits": 0,
                "description": "Overview of anomalies across all AWS accounts",
                "panelsJSON": json.dumps([
                    {
                        "id": "1",
                        "type": "visualization",
                        "title": "Anomalies by Account",
                        "visualization": {
                            "visType": "pie",
                            "params": {
                                "addTooltip": True,
                                "addLegend": True,
                                "legendPosition": "right"
                            }
                        }
                    },
                    {
                        "id": "2",
                        "type": "visualization",
                        "title": "Anomaly Timeline",
                        "visualization": {
                            "visType": "line",
                            "params": {
                                "grid": {"categoryLines": False, "style": {"color": "#eee"}}
                            }
                        }
                    }
                ])
            }
        }
    ]
    
    # Create visualizations and dashboards
    for dashboard in dashboards:
        opensearch_request(
            'POST',
            '/_dashboards/api/saved_objects/dashboard',
            dashboard
        )
    
    print("Created cross-account dashboards")


def cleanup_detectors():
    """
    Clean up detectors during stack deletion
    """
    try:
        # List all detectors
        detectors_response = opensearch_request('GET', '/_plugins/_anomaly_detection/detectors')
        detectors = detectors_response.get('detectors', [])
        
        # Find multi-account detectors
        multi_account_detectors = [d for d in detectors if 'multi-account' in d.get('name', '')]
        
        for detector in multi_account_detectors:
            detector_id = detector['_id']
            detector_name = detector['name']
            
            try:
                # Stop the detector
                opensearch_request('POST', f'/_plugins/_anomaly_detection/detectors/{detector_id}/_stop')
                print(f"Stopped detector {detector_name}")
                
                # Delete the detector
                opensearch_request('DELETE', f'/_plugins/_anomaly_detection/detectors/{detector_id}')
                print(f"Deleted detector {detector_name}")
                
            except Exception as e:
                print(f"Error cleaning up detector {detector_name}: {str(e)}")
        
        print(f"Cleanup completed for {len(multi_account_detectors)} detectors")
        
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")


def opensearch_request(method, path, body=None):
    """
    Make authenticated request to OpenSearch using AWS IAM
    """
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    import urllib3
    
    url = f"https://{OPENSEARCH_HOST}{path}"
    headers = {'Content-Type': 'application/json'}
    
    # Create AWS request for signing
    request = AWSRequest(method=method, url=url, data=json.dumps(body) if body else None, headers=headers)
    
    # Sign the request with AWS credentials
    credentials = boto3.Session().get_credentials()
    SigV4Auth(credentials, 'es', AWS_REGION).add_auth(request)
    
    # Make the request
    http = urllib3.PoolManager()
    response = http.request(
        method,
        url,
        body=request.body,
        headers=dict(request.headers)
    )
    
    if response.status >= 400:
        raise Exception(f"OpenSearch request failed with status {response.status}: {response.data.decode()}")
    
    return json.loads(response.data.decode()) if response.data else {}
