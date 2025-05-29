import json
import os
import boto3  # type: ignore
import requests
from requests.auth import HTTPBasicAuth
import time
from datetime import datetime

# Environment variables
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST')
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME', 'admin')
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD', 'admin')
ENABLE_MULTI_ACCOUNT = os.environ.get('ENABLE_MULTI_ACCOUNT', 'true').lower() == 'true'

# Initialize AWS clients
organizations = boto3.client('organizations')


def handler(event, context):
    """
    Lambda handler to configure multi-account anomaly detectors
    """
    print(f"Event: {json.dumps(event)}")
    
    request_type = event.get('RequestType', 'Create')
    
    try:
        if request_type in ['Create', 'Update']:
            # Get organization accounts
            accounts = get_organization_accounts()
            print(f"Found {len(accounts)} accounts in organization")
            
            # Create multi-account anomaly detectors
            detectors = event['ResourceProperties'].get('detectors', [])
            results = []
            
            for detector_config in detectors:
                result = create_multi_account_detector(detector_config, accounts)
                results.append(result)
            
            # Create cross-account dashboards
            create_cross_account_dashboards()
            
            return {
                'PhysicalResourceId': f'multi-account-detectors-{context.request_id}',
                'Data': {
                    'DetectorsCreated': len(results),
                    'AccountsMonitored': len(accounts)
                }
            }
            
        elif request_type == 'Delete':
            # Clean up detectors if needed
            print("Delete request - no cleanup needed")
            return {
                'PhysicalResourceId': event.get('PhysicalResourceId', 'deleted')
            }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        raise


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


def opensearch_request(method, path, body=None):
    """
    Make authenticated request to OpenSearch
    """
    url = f"https://{OPENSEARCH_HOST}{path}"
    auth = HTTPBasicAuth(OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD)
    headers = {'Content-Type': 'application/json'}
    
    response = requests.request(
        method,
        url,
        auth=auth,
        headers=headers,
        json=body,
        verify=False  # In production, use proper SSL verification
    )
    
    response.raise_for_status()
    return response.json() if response.text else {}
