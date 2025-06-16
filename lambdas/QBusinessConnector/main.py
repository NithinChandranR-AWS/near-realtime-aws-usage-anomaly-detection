import json
import os
import boto3  # type: ignore
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any
import hashlib
import time

# Environment variables
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST')
Q_APPLICATION_ID = os.environ.get('Q_APPLICATION_ID')
Q_INDEX_ID = os.environ.get('Q_INDEX_ID')
SYNC_INTERVAL_MINUTES = int(os.environ.get('SYNC_INTERVAL_MINUTES', '15'))

# AWS clients
q_business = boto3.client('qbusiness')
opensearch_client = boto3.client('es')


def handler(event, context):
    """
    Lambda handler to sync anomaly data from OpenSearch to Amazon Q for Business
    """
    print(f"Starting Q Business sync at {datetime.utcnow()}")
    
    try:
        # Get recent anomaly data from OpenSearch
        anomalies = fetch_recent_anomalies()
        print(f"Found {len(anomalies)} anomalies to sync")
        
        # Transform anomalies into Q Business documents
        documents = transform_anomalies_to_documents(anomalies)
        
        # Sync documents to Q Business
        sync_results = sync_documents_to_q(documents)
        
        # Update sync metadata
        update_sync_metadata(sync_results)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Sync completed successfully',
                'anomalies_processed': len(anomalies),
                'documents_synced': sync_results['success_count'],
                'sync_time': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Error during sync: {str(e)}")
        raise


def fetch_recent_anomalies():
    """
    Fetch recent anomalies from OpenSearch
    """
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=SYNC_INTERVAL_MINUTES)
    
    # OpenSearch query for anomalies
    query = {
        "query": {
            "bool": {
                "must": [
                    {
                        "range": {
                            "eventTime": {
                                "gte": start_time.isoformat(),
                                "lte": end_time.isoformat()
                            }
                        }
                    },
                    {
                        "terms": {
                            "eventName.keyword": ["RunInstances", "CreateVolume", "Invoke"]
                        }
                    }
                ]
            }
        },
        "aggs": {
            "by_account": {
                "terms": {
                    "field": "recipientAccountId",
                    "size": 100
                },
                "aggs": {
                    "by_event": {
                        "terms": {
                            "field": "eventName.keyword"
                        },
                        "aggs": {
                            "event_details": {
                                "top_hits": {
                                    "size": 10,
                                    "_source": [
                                        "eventTime",
                                        "awsRegion",
                                        "userIdentity",
                                        "sourceIPAddress",
                                        "requestParameters",
                                        "accountAlias",
                                        "accountType"
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        },
        "size": 0
    }
    
    # Execute query
    response = opensearch_request('POST', '/cwl-multiaccounts*/_search', query)
    
    # Parse results
    anomalies = []
    for account_bucket in response['aggregations']['by_account']['buckets']:
        account_id = account_bucket['key']
        
        for event_bucket in account_bucket['by_event']['buckets']:
            event_name = event_bucket['key']
            events = event_bucket['event_details']['hits']['hits']
            
            anomaly = {
                'account_id': account_id,
                'event_name': event_name,
                'event_count': event_bucket['doc_count'],
                'events': [hit['_source'] for hit in events],
                'time_range': {
                    'start': start_time.isoformat(),
                    'end': end_time.isoformat()
                }
            }
            anomalies.append(anomaly)
    
    return anomalies


def transform_anomalies_to_documents(anomalies: List[Dict]) -> List[Dict]:
    """
    Transform anomaly data into Q Business document format
    """
    documents = []
    
    for anomaly in anomalies:
        # Create unique document ID
        doc_id = hashlib.sha256(
            f"{anomaly['account_id']}-{anomaly['event_name']}-{anomaly['time_range']['start']}".encode()
        ).hexdigest()
        
        # Extract account info
        account_info = anomaly['events'][0] if anomaly['events'] else {}
        account_alias = account_info.get('accountAlias', anomaly['account_id'])
        account_type = account_info.get('accountType', 'unknown')
        
        # Build document content
        content = f"""
Anomaly Alert: {anomaly['event_name']} in Account {account_alias}

Summary:
- Account ID: {anomaly['account_id']}
- Account Type: {account_type}
- Event Type: {anomaly['event_name']}
- Event Count: {anomaly['event_count']}
- Time Period: {anomaly['time_range']['start']} to {anomaly['time_range']['end']}

Details:
"""
        
        # Add event details
        for i, event in enumerate(anomaly['events'][:5]):  # Limit to 5 events
            content += f"""
Event {i+1}:
- Time: {event.get('eventTime', 'Unknown')}
- Region: {event.get('awsRegion', 'Unknown')}
- User: {event.get('userIdentity', {}).get('type', 'Unknown')}
- Source IP: {event.get('sourceIPAddress', 'Unknown')}
"""
        
        # Add context based on event type
        if anomaly['event_name'] == 'RunInstances':
            content += "\nContext: EC2 instance launches detected. This could indicate:\n"
            content += "- Normal scaling activities\n"
            content += "- Potential unauthorized instance creation\n"
            content += "- Cost implications from unexpected compute usage\n"
        elif anomaly['event_name'] == 'CreateVolume':
            content += "\nContext: EBS volume creation detected. This could indicate:\n"
            content += "- Normal storage provisioning\n"
            content += "- Potential data exfiltration preparation\n"
            content += "- Cost implications from storage expansion\n"
        elif anomaly['event_name'] == 'Invoke':
            content += "\nContext: Lambda function invocations detected. This could indicate:\n"
            content += "- Normal application activity\n"
            content += "- Potential runaway functions\n"
            content += "- Cost implications from excessive invocations\n"
        
        # Create Q Business document
        document = {
            'id': doc_id,
            'type': 'ANOMALY_REPORT',
            'title': f"{anomaly['event_name']} Anomaly - {account_alias}",
            'content': {
                'text': content
            },
            'attributes': {
                'account_id': anomaly['account_id'],
                'account_alias': account_alias,
                'account_type': account_type,
                'event_name': anomaly['event_name'],
                'event_count': str(anomaly['event_count']),
                'anomaly_date': anomaly['time_range']['start'],
                'severity': calculate_severity(anomaly)
            },
            'contentType': 'PLAIN_TEXT',
            'accessConfiguration': {
                'accessControls': [
                    {
                        'principals': [
                            {
                                'group': {
                                    'access': 'ALLOW',
                                    'name': 'security-team'
                                }
                            }
                        ]
                    }
                ]
            }
        }
        
        documents.append(document)
    
    return documents


def calculate_severity(anomaly: Dict) -> str:
    """
    Calculate severity based on event count and type
    """
    event_count = anomaly['event_count']
    event_name = anomaly['event_name']
    
    # Define thresholds per event type
    severity_thresholds = {
        'RunInstances': {'low': 5, 'medium': 10, 'high': 20},
        'CreateVolume': {'low': 10, 'medium': 20, 'high': 50},
        'Invoke': {'low': 1000, 'medium': 5000, 'high': 10000}
    }
    
    thresholds = severity_thresholds.get(event_name, {'low': 10, 'medium': 50, 'high': 100})
    
    if event_count >= thresholds['high']:
        return 'HIGH'
    elif event_count >= thresholds['medium']:
        return 'MEDIUM'
    elif event_count >= thresholds['low']:
        return 'LOW'
    else:
        return 'INFO'


def sync_documents_to_q(documents: List[Dict]) -> Dict:
    """
    Sync documents to Amazon Q for Business
    """
    success_count = 0
    error_count = 0
    
    # Batch documents for efficiency
    batch_size = 10
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        
        try:
            # Format documents for Q Business API
            batch_documents = []
            for doc in batch:
                batch_documents.append({
                    'id': doc['id'],
                    'type': doc['type'],
                    'title': doc['title'],
                    'content': doc['content'],
                    'attributes': [
                        {'name': k, 'value': {'stringValue': v}}
                        for k, v in doc['attributes'].items()
                    ],
                    'contentType': doc['contentType'],
                    'accessConfiguration': doc['accessConfiguration']
                })
            
            # Send batch to Q Business
            response = q_business.batch_put_document(
                applicationId=Q_APPLICATION_ID,
                indexId=Q_INDEX_ID,
                documents=batch_documents
            )
            
            # Count successes and failures
            success_count += len(response.get('successfulDocuments', []))
            error_count += len(response.get('failedDocuments', []))
            
            # Log any failures
            for failed in response.get('failedDocuments', []):
                print(f"Failed to sync document {failed['id']}: {failed['error']}")
            
        except Exception as e:
            print(f"Error syncing batch: {str(e)}")
            error_count += len(batch)
    
    return {
        'success_count': success_count,
        'error_count': error_count,
        'total_documents': len(documents)
    }


def update_sync_metadata(sync_results: Dict):
    """
    Update sync metadata in DynamoDB or S3 for tracking
    """
    metadata = {
        'last_sync_time': datetime.utcnow().isoformat(),
        'documents_synced': sync_results['success_count'],
        'sync_errors': sync_results['error_count'],
        'sync_status': 'success' if sync_results['error_count'] == 0 else 'partial_failure'
    }
    
    # In production, store this in DynamoDB or S3
    print(f"Sync metadata: {json.dumps(metadata)}")


def opensearch_request(method: str, path: str, body: Dict = None) -> Dict:
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
    SigV4Auth(credentials, 'es', os.environ.get('AWS_REGION', 'us-east-1')).add_auth(request)
    
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
