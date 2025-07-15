import json
import os
import boto3
import logging
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', '')
LOGS_FUNCTION_NAME = os.environ.get('LOGS_FUNCTION_NAME', '')
Q_CONNECTOR_FUNCTION_NAME = os.environ.get('Q_CONNECTOR_FUNCTION_NAME', '')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')

# Initialize AWS clients
cloudwatch = boto3.client('cloudwatch')
lambda_client = boto3.client('lambda')
logs_client = boto3.client('logs')
sns = boto3.client('sns')

def handler(event, context):
    """System health monitoring handler"""
    logger.info("Starting system health monitoring")
    
    try:
        # Collect health metrics
        health_metrics = collect_health_metrics()
        
        # Publish custom metrics to CloudWatch
        publish_custom_metrics(health_metrics)
        
        # Check for critical issues and send alerts if needed
        check_critical_issues(health_metrics)
        
        logger.info("System health monitoring completed successfully")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Health monitoring completed',
                'metrics': health_metrics
            })
        }
        
    except Exception as e:
        logger.error(f"Error in system health monitoring: {str(e)}")
        
        # Send alert about monitoring failure
        try:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject="System Health Monitoring Failed",
                Message=f"System health monitoring failed with error: {str(e)}"
            )
        except Exception as sns_error:
            logger.error(f"Failed to send monitoring failure alert: {str(sns_error)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f'Health monitoring failed: {str(e)}'
            })
        }

def collect_health_metrics():
    """Collect various health metrics from the system"""
    metrics = {}
    
    # Lambda function health
    metrics['lambda_health'] = check_lambda_health()
    
    # OpenSearch health
    if OPENSEARCH_ENDPOINT:
        metrics['opensearch_health'] = check_opensearch_health()
    
    # Log processing metrics
    metrics['log_processing'] = check_log_processing_metrics()
    
    # Overall system health score
    metrics['overall_health_score'] = calculate_overall_health_score(metrics)
    
    return metrics

def check_lambda_health():
    """Check health of Lambda functions"""
    lambda_health = {}
    
    functions_to_check = [
        LOGS_FUNCTION_NAME,
        Q_CONNECTOR_FUNCTION_NAME
    ]
    
    for function_name in functions_to_check:
        if not function_name:
            continue
            
        try:
            # Get function configuration
            response = lambda_client.get_function(FunctionName=function_name)
            
            # Get recent invocation metrics
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=15)
            
            # Get error rate
            error_metrics = cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Errors',
                Dimensions=[
                    {
                        'Name': 'FunctionName',
                        'Value': function_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Sum']
            )
            
            # Get invocation count
            invocation_metrics = cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[
                    {
                        'Name': 'FunctionName',
                        'Value': function_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,
                Statistics=['Sum']
            )
            
            # Calculate error rate
            total_errors = sum([point['Sum'] for point in error_metrics['Datapoints']])
            total_invocations = sum([point['Sum'] for point in invocation_metrics['Datapoints']])
            error_rate = (total_errors / total_invocations * 100) if total_invocations > 0 else 0
            
            lambda_health[function_name] = {
                'status': 'healthy' if error_rate < 5 else 'unhealthy',
                'error_rate': error_rate,
                'total_errors': total_errors,
                'total_invocations': total_invocations,
                'last_modified': response['Configuration']['LastModified']
            }
            
        except Exception as e:
            logger.error(f"Error checking health for function {function_name}: {str(e)}")
            lambda_health[function_name] = {
                'status': 'error',
                'error': str(e)
            }
    
    return lambda_health

def check_opensearch_health():
    """Check OpenSearch cluster health"""
    try:
        import requests
        from requests_aws4auth import AWS4Auth
        
        # Get AWS credentials for signing requests
        session = boto3.Session()
        credentials = session.get_credentials()
        region = session.region_name or 'us-east-1'
        
        # Create AWS4Auth object
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            'es',
            session_token=credentials.token
        )
        
        # Check cluster health
        health_url = f"https://{OPENSEARCH_ENDPOINT}/_cluster/health"
        response = requests.get(health_url, auth=awsauth, timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            return {
                'status': health_data.get('status', 'unknown'),
                'cluster_name': health_data.get('cluster_name', 'unknown'),
                'number_of_nodes': health_data.get('number_of_nodes', 0),
                'active_primary_shards': health_data.get('active_primary_shards', 0),
                'active_shards': health_data.get('active_shards', 0),
                'relocating_shards': health_data.get('relocating_shards', 0),
                'initializing_shards': health_data.get('initializing_shards', 0),
                'unassigned_shards': health_data.get('unassigned_shards', 0)
            }
        else:
            return {
                'status': 'error',
                'error': f'HTTP {response.status_code}: {response.text}'
            }
            
    except Exception as e:
        logger.error(f"Error checking OpenSearch health: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }

def check_log_processing_metrics():
    """Check log processing metrics"""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        # Check for recent log processing activity
        log_groups = [
            '/aws/lambda/' + LOGS_FUNCTION_NAME,
            '/aws/lambda/' + Q_CONNECTOR_FUNCTION_NAME
        ]
        
        processing_metrics = {}
        
        for log_group in log_groups:
            if not log_group.endswith('/'):
                try:
                    # Get recent log events
                    response = logs_client.filter_log_events(
                        logGroupName=log_group,
                        startTime=int(start_time.timestamp() * 1000),
                        endTime=int(end_time.timestamp() * 1000),
                        filterPattern='ERROR'
                    )
                    
                    error_count = len(response.get('events', []))
                    
                    # Get total events
                    total_response = logs_client.filter_log_events(
                        logGroupName=log_group,
                        startTime=int(start_time.timestamp() * 1000),
                        endTime=int(end_time.timestamp() * 1000)
                    )
                    
                    total_count = len(total_response.get('events', []))
                    
                    processing_metrics[log_group] = {
                        'error_count': error_count,
                        'total_events': total_count,
                        'error_rate': (error_count / total_count * 100) if total_count > 0 else 0
                    }
                    
                except Exception as e:
                    logger.warning(f"Could not get metrics for log group {log_group}: {str(e)}")
                    processing_metrics[log_group] = {
                        'status': 'error',
                        'error': str(e)
                    }
        
        return processing_metrics
        
    except Exception as e:
        logger.error(f"Error checking log processing metrics: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }

def calculate_overall_health_score(metrics):
    """Calculate overall system health score (0-100)"""
    try:
        score = 100
        
        # Lambda health impact
        lambda_health = metrics.get('lambda_health', {})
        for function_name, health in lambda_health.items():
            if health.get('status') == 'unhealthy':
                score -= 20
            elif health.get('status') == 'error':
                score -= 30
            elif health.get('error_rate', 0) > 1:
                score -= 10
        
        # OpenSearch health impact
        opensearch_health = metrics.get('opensearch_health', {})
        if opensearch_health.get('status') == 'red':
            score -= 40
        elif opensearch_health.get('status') == 'yellow':
            score -= 20
        elif opensearch_health.get('status') == 'error':
            score -= 30
        
        # Log processing impact
        log_processing = metrics.get('log_processing', {})
        for log_group, processing in log_processing.items():
            if processing.get('error_rate', 0) > 10:
                score -= 15
            elif processing.get('error_rate', 0) > 5:
                score -= 10
        
        return max(0, score)  # Ensure score doesn't go below 0
        
    except Exception as e:
        logger.error(f"Error calculating health score: {str(e)}")
        return 50  # Return neutral score on error

def publish_custom_metrics(metrics):
    """Publish custom metrics to CloudWatch"""
    try:
        metric_data = []
        
        # Overall health score
        health_score = metrics.get('overall_health_score', 50)
        metric_data.append({
            'MetricName': 'OverallHealthScore',
            'Value': health_score,
            'Unit': 'Percent',
            'Timestamp': datetime.utcnow()
        })
        
        # Lambda function health metrics
        lambda_health = metrics.get('lambda_health', {})
        for function_name, health in lambda_health.items():
            if 'error_rate' in health:
                metric_data.append({
                    'MetricName': 'LambdaErrorRate',
                    'Value': health['error_rate'],
                    'Unit': 'Percent',
                    'Dimensions': [
                        {
                            'Name': 'FunctionName',
                            'Value': function_name
                        }
                    ],
                    'Timestamp': datetime.utcnow()
                })
        
        # OpenSearch health metrics
        opensearch_health = metrics.get('opensearch_health', {})
        if 'unassigned_shards' in opensearch_health:
            metric_data.append({
                'MetricName': 'OpenSearchUnassignedShards',
                'Value': opensearch_health['unassigned_shards'],
                'Unit': 'Count',
                'Timestamp': datetime.utcnow()
            })
        
        # Processing success rate
        log_processing = metrics.get('log_processing', {})
        total_events = 0
        total_errors = 0
        
        for log_group, processing in log_processing.items():
            if 'total_events' in processing and 'error_count' in processing:
                total_events += processing['total_events']
                total_errors += processing['error_count']
        
        if total_events > 0:
            success_rate = ((total_events - total_errors) / total_events) * 100
            metric_data.append({
                'MetricName': 'ProcessingSuccessRate',
                'Value': success_rate,
                'Unit': 'Percent',
                'Timestamp': datetime.utcnow()
            })
        
        # Publish metrics in batches (CloudWatch limit is 20 per call)
        for i in range(0, len(metric_data), 20):
            batch = metric_data[i:i+20]
            cloudwatch.put_metric_data(
                Namespace='MultiAccountAnomalyDetection',
                MetricData=batch
            )
        
        logger.info(f"Published {len(metric_data)} custom metrics to CloudWatch")
        
    except Exception as e:
        logger.error(f"Error publishing custom metrics: {str(e)}")

def check_critical_issues(metrics):
    """Check for critical issues and send alerts"""
    try:
        critical_issues = []
        
        # Check overall health score
        health_score = metrics.get('overall_health_score', 100)
        if health_score < 50:
            critical_issues.append(f"Overall system health score is critically low: {health_score}%")
        
        # Check Lambda function health
        lambda_health = metrics.get('lambda_health', {})
        for function_name, health in lambda_health.items():
            if health.get('status') == 'error':
                critical_issues.append(f"Lambda function {function_name} is in error state: {health.get('error', 'Unknown error')}")
            elif health.get('error_rate', 0) > 10:
                critical_issues.append(f"Lambda function {function_name} has high error rate: {health['error_rate']:.1f}%")
        
        # Check OpenSearch health
        opensearch_health = metrics.get('opensearch_health', {})
        if opensearch_health.get('status') == 'red':
            critical_issues.append("OpenSearch cluster status is RED - immediate attention required")
        elif opensearch_health.get('unassigned_shards', 0) > 0:
            critical_issues.append(f"OpenSearch has {opensearch_health['unassigned_shards']} unassigned shards")
        
        # Send alert if critical issues found
        if critical_issues and SNS_TOPIC_ARN:
            message = "CRITICAL SYSTEM HEALTH ALERT\n\n"
            message += "The following critical issues have been detected:\n\n"
            for issue in critical_issues:
                message += f"• {issue}\n"
            message += f"\nOverall Health Score: {health_score}%\n"
            message += f"Timestamp: {datetime.utcnow().isoformat()}\n"
            
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject="CRITICAL: Multi-Account Anomaly Detection System Health Alert",
                Message=message
            )
            
            logger.warning(f"Sent critical health alert for {len(critical_issues)} issues")
        
    except Exception as e:
        logger.error(f"Error checking critical issues: {str(e)}")