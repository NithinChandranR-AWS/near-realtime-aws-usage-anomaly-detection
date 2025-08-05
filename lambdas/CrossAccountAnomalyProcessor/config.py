#!/usr/bin/env python3
"""
Cross-Account Anomaly Configuration Handler

This Lambda function configures OpenSearch anomaly detectors for multi-account
CloudTrail log analysis with account-specific categorization.
"""

import json
import os
import boto3
import requests
from requests_aws4auth import AWS4Auth
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST')
ENABLE_MULTI_ACCOUNT = os.environ.get('ENABLE_MULTI_ACCOUNT', 'false').lower() == 'true'

# AWS clients
session = boto3.Session()
credentials = session.get_credentials()
region = session.region_name or 'us-east-1'
service = 'es'
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

def handler(event, context):
    """
    CloudFormation custom resource handler for configuring multi-account anomaly detectors
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    request_type = event.get('RequestType')
    properties = event.get('ResourceProperties', {})
    
    try:
        if request_type == 'Create':
            response = create_anomaly_detectors(properties)
        elif request_type == 'Update':
            response = update_anomaly_detectors(properties)
        elif request_type == 'Delete':
            response = delete_anomaly_detectors(properties)
        else:
            raise ValueError(f"Unknown request type: {request_type}")
        
        send_response(event, context, 'SUCCESS', response)
        
    except Exception as e:
        logger.error(f"Error handling request: {str(e)}")
        send_response(event, context, 'FAILED', {'Error': str(e)})

def create_anomaly_detectors(properties):
    """Create multi-account anomaly detectors"""
    logger.info("Creating multi-account anomaly detectors")
    
    detectors = properties.get('detectors', [])
    results = []
    
    # First, ensure the index template exists
    create_index_template()
    
    # Create OpenSearch dashboards for multi-account visualization
    create_multi_account_dashboards()
    
    for detector_config in detectors:
        try:
            detector_name = detector_config['name']
            category_fields = detector_config['category_fields']
            
            # Create anomaly detector
            detector_body = {
                "name": detector_name,
                "description": f"Multi-account anomaly detector for {detector_name}",
                "time_field": "@timestamp",
                "indices": ["cwl-multiaccounts*"],
                "feature_attributes": [
                    {
                        "feature_name": "event_count",
                        "feature_enabled": True,
                        "aggregation_query": {
                            "event_count": {
                                "value_count": {
                                    "field": "eventName.keyword"
                                }
                            }
                        }
                    }
                ],
                "window_delay": {
                    "period": {
                        "interval": 1,
                        "unit": "Minutes"
                    }
                },
                "detection_interval": {
                    "period": {
                        "interval": 10,
                        "unit": "Minutes"
                    }
                },
                "category_field": category_fields
            }
            
            # Add event-specific filters
            if 'ec2' in detector_name:
                detector_body['filter_query'] = {
                    "bool": {
                        "must": [
                            {"term": {"eventName.keyword": "RunInstances"}}
                        ]
                    }
                }
            elif 'lambda' in detector_name:
                detector_body['filter_query'] = {
                    "bool": {
                        "must": [
                            {"term": {"eventName.keyword": "Invoke"}}
                        ]
                    }
                }
            elif 'ebs' in detector_name:
                detector_body['filter_query'] = {
                    "bool": {
                        "must": [
                            {"term": {"eventName.keyword": "CreateVolume"}}
                        ]
                    }
                }
            
            # Create the detector
            url = f"https://{OPENSEARCH_HOST}/_plugins/_anomaly_detection/detectors"
            response = requests.post(url, auth=awsauth, json=detector_body, headers={'Content-Type': 'application/json'})
            
            if response.status_code in [200, 201]:
                detector_id = response.json().get('_id')
                logger.info(f"Created detector {detector_name} with ID: {detector_id}")
                
                # Start the detector
                start_detector(detector_id)
                
                results.append({
                    'name': detector_name,
                    'id': detector_id,
                    'status': 'created'
                })
            else:
                logger.error(f"Failed to create detector {detector_name}: {response.text}")
                results.append({
                    'name': detector_name,
                    'status': 'failed',
                    'error': response.text
                })
                
        except Exception as e:
            logger.error(f"Error creating detector {detector_config.get('name', 'unknown')}: {str(e)}")
            results.append({
                'name': detector_config.get('name', 'unknown'),
                'status': 'failed',
                'error': str(e)
            })
    
    return {'detectors': results}

def create_index_template():
    """Create index template for multi-account logs"""
    template_body = {
        "index_patterns": ["cwl-multiaccounts*"],
        "template": {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
                "index.refresh_interval": "30s"
            },
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "eventTime": {"type": "date"},
                    "eventName": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword"}
                        }
                    },
                    "recipientAccountId": {"type": "keyword"},
                    "accountAlias": {"type": "keyword"},
                    "accountType": {"type": "keyword"},
                    "organizationId": {"type": "keyword"},
                    "organizationalUnit": {"type": "keyword"},
                    "costCenter": {"type": "keyword"},
                    "awsRegion": {"type": "keyword"},
                    "sourceIPAddress": {"type": "ip"},
                    "userIdentity.type": {"type": "keyword"},
                    "eventSource": {"type": "keyword"}
                }
            }
        }
    }
    
    url = f"https://{OPENSEARCH_HOST}/_index_template/cwl-multiaccounts-template"
    response = requests.put(url, auth=awsauth, json=template_body, headers={'Content-Type': 'application/json'})
    
    if response.status_code in [200, 201]:
        logger.info("Created index template for multi-account logs")
    else:
        logger.warning(f"Failed to create index template: {response.text}")

def create_multi_account_dashboards():
    """Create OpenSearch dashboards for multi-account anomaly visualization"""
    logger.info("Creating multi-account dashboards")
    
    # Create index pattern for multi-account logs
    index_pattern_body = {
        "attributes": {
            "title": "cwl-multiaccounts*",
            "timeFieldName": "@timestamp"
        }
    }
    
    url = f"https://{OPENSEARCH_HOST}/_dashboards/api/saved_objects/index-pattern/cwl-multiaccounts"
    response = requests.post(url, auth=awsauth, json=index_pattern_body, 
                           headers={'Content-Type': 'application/json', 'osd-xsrf': 'true'})
    
    if response.status_code in [200, 409]:  # 409 means already exists
        logger.info("Created/verified index pattern for multi-account logs")
    else:
        logger.warning(f"Failed to create index pattern: {response.text}")
    
    # Create visualization for account distribution
    account_viz_body = {
        "attributes": {
            "title": "Multi-Account Event Distribution",
            "visState": json.dumps({
                "title": "Multi-Account Event Distribution",
                "type": "pie",
                "params": {
                    "addTooltip": True,
                    "addLegend": True,
                    "legendPosition": "right"
                },
                "aggs": [
                    {
                        "id": "1",
                        "enabled": True,
                        "type": "count",
                        "schema": "metric",
                        "params": {}
                    },
                    {
                        "id": "2",
                        "enabled": True,
                        "type": "terms",
                        "schema": "segment",
                        "params": {
                            "field": "accountAlias.keyword",
                            "size": 10,
                            "order": "desc",
                            "orderBy": "1"
                        }
                    }
                ]
            }),
            "uiStateJSON": "{}",
            "description": "Distribution of events across AWS accounts",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "index": "cwl-multiaccounts",
                    "query": {
                        "match_all": {}
                    }
                })
            }
        }
    }
    
    url = f"https://{OPENSEARCH_HOST}/_dashboards/api/saved_objects/visualization/multi-account-distribution"
    response = requests.post(url, auth=awsauth, json=account_viz_body,
                           headers={'Content-Type': 'application/json', 'osd-xsrf': 'true'})
    
    if response.status_code in [200, 409]:
        logger.info("Created/verified account distribution visualization")
    else:
        logger.warning(f"Failed to create visualization: {response.text}")

def start_detector(detector_id):
    """Start an anomaly detector"""
    url = f"https://{OPENSEARCH_HOST}/_plugins/_anomaly_detection/detectors/{detector_id}/_start"
    response = requests.post(url, auth=awsauth, headers={'Content-Type': 'application/json'})
    
    if response.status_code == 200:
        logger.info(f"Started detector {detector_id}")
    else:
        logger.warning(f"Failed to start detector {detector_id}: {response.text}")

def update_anomaly_detectors(properties):
    """Update existing anomaly detectors"""
    logger.info("Updating multi-account anomaly detectors")
    # For simplicity, recreate detectors on update
    delete_anomaly_detectors(properties)
    return create_anomaly_detectors(properties)

def delete_anomaly_detectors(properties):
    """Delete anomaly detectors and cleanup resources"""
    logger.info("Deleting multi-account anomaly detectors")
    
    try:
        # Delete anomaly detectors
        delete_detectors()
        
        # Delete dashboards and visualizations
        delete_dashboards()
        
        # Delete index template (optional - may want to keep for future deployments)
        delete_index_template()
        
        return {'status': 'deleted'}
        
    except Exception as e:
        logger.error(f"Error deleting resources: {str(e)}")
        return {'status': 'error', 'error': str(e)}

def delete_detectors():
    """Delete all multi-account anomaly detectors"""
    # List all detectors and delete ones matching our naming pattern
    url = f"https://{OPENSEARCH_HOST}/_plugins/_anomaly_detection/detectors/_search"
    search_body = {
        "query": {
            "bool": {
                "should": [
                    {"wildcard": {"name": "multi-account-*"}}
                ]
            }
        }
    }
    
    response = requests.post(url, auth=awsauth, json=search_body, headers={'Content-Type': 'application/json'})
    
    if response.status_code == 200:
        detectors = response.json().get('hits', {}).get('hits', [])
        
        for detector in detectors:
            detector_id = detector['_id']
            detector_name = detector['_source']['name']
            
            # Stop detector first
            stop_url = f"https://{OPENSEARCH_HOST}/_plugins/_anomaly_detection/detectors/{detector_id}/_stop"
            requests.post(stop_url, auth=awsauth)
            
            # Delete detector
            delete_url = f"https://{OPENSEARCH_HOST}/_plugins/_anomaly_detection/detectors/{detector_id}"
            delete_response = requests.delete(delete_url, auth=awsauth)
            
            if delete_response.status_code == 200:
                logger.info(f"Deleted detector {detector_name}")
            else:
                logger.warning(f"Failed to delete detector {detector_name}: {delete_response.text}")

def delete_dashboards():
    """Delete multi-account dashboards and visualizations"""
    # Delete visualization
    viz_url = f"https://{OPENSEARCH_HOST}/_dashboards/api/saved_objects/visualization/multi-account-distribution"
    response = requests.delete(viz_url, auth=awsauth, headers={'osd-xsrf': 'true'})
    
    if response.status_code in [200, 404]:  # 404 means already deleted
        logger.info("Deleted multi-account visualization")
    else:
        logger.warning(f"Failed to delete visualization: {response.text}")
    
    # Delete index pattern
    pattern_url = f"https://{OPENSEARCH_HOST}/_dashboards/api/saved_objects/index-pattern/cwl-multiaccounts"
    response = requests.delete(pattern_url, auth=awsauth, headers={'osd-xsrf': 'true'})
    
    if response.status_code in [200, 404]:
        logger.info("Deleted multi-account index pattern")
    else:
        logger.warning(f"Failed to delete index pattern: {response.text}")

def delete_index_template():
    """Delete the multi-account index template"""
    url = f"https://{OPENSEARCH_HOST}/_index_template/cwl-multiaccounts-template"
    response = requests.delete(url, auth=awsauth)
    
    if response.status_code in [200, 404]:
        logger.info("Deleted multi-account index template")
    else:
        logger.warning(f"Failed to delete index template: {response.text}")

def send_response(event, context, response_status, response_data):
    """Send response to CloudFormation"""
    response_url = event.get('ResponseURL')
    if not response_url:
        logger.info("No ResponseURL provided, skipping CloudFormation response")
        return
    
    response_body = {
        'Status': response_status,
        'Reason': f'See CloudWatch Log Stream: {context.log_stream_name}',
        'PhysicalResourceId': context.log_stream_name,
        'StackId': event.get('StackId'),
        'RequestId': event.get('RequestId'),
        'LogicalResourceId': event.get('LogicalResourceId'),
        'Data': response_data
    }
    
    try:
        response = requests.put(response_url, json=response_body)
        logger.info(f"CloudFormation response sent: {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to send CloudFormation response: {str(e)}")