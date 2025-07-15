import json
import os
import boto3
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', '')
SOURCE_FUNCTION = os.environ.get('SOURCE_FUNCTION', 'Unknown')

# Initialize AWS clients
sns = boto3.client('sns')
cloudwatch = boto3.client('cloudwatch')

def handler(event, context):
    """Handle failed events from Lambda functions"""
    logger.info(f"Processing dead letter queue event from {SOURCE_FUNCTION}")
    logger.info(f"Event: {json.dumps(event)}")
    
    try:
        # Extract failure information
        failure_info = extract_failure_info(event)
        
        # Publish failure metrics
        publish_failure_metrics(failure_info)
        
        # Send alert notification
        send_failure_alert(failure_info)
        
        # Log failure details for debugging
        log_failure_details(failure_info)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Dead letter queue event processed successfully',
                'source_function': SOURCE_FUNCTION,
                'failure_count': len(failure_info.get('failed_records', []))
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing dead letter queue event: {str(e)}")
        
        # Try to send a basic alert about DLQ processing failure
        try:
            if SNS_TOPIC_ARN:
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Subject=f"DLQ Processing Failed - {SOURCE_FUNCTION}",
                    Message=f"Failed to process dead letter queue event from {SOURCE_FUNCTION}: {str(e)}"
                )
        except Exception as sns_error:
            logger.error(f"Failed to send DLQ processing failure alert: {str(sns_error)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f'Failed to process DLQ event: {str(e)}'
            })
        }

def extract_failure_info(event):
    """Extract failure information from the event"""
    failure_info = {
        'timestamp': datetime.utcnow().isoformat(),
        'source_function': SOURCE_FUNCTION,
        'failed_records': [],
        'error_types': {},
        'total_failures': 0
    }
    
    try:
        # Handle different event structures
        if 'Records' in event:
            # SQS/SNS records
            for record in event['Records']:
                failure_record = {
                    'record_id': record.get('messageId', 'unknown'),
                    'body': record.get('body', ''),
                    'attributes': record.get('attributes', {}),
                    'source': record.get('eventSource', 'unknown')
                }
                
                # Try to extract error information from the body
                try:
                    body = json.loads(record.get('body', '{}'))
                    if 'errorMessage' in body:
                        failure_record['error_message'] = body['errorMessage']
                        failure_record['error_type'] = body.get('errorType', 'Unknown')
                        
                        # Count error types
                        error_type = failure_record['error_type']
                        failure_info['error_types'][error_type] = failure_info['error_types'].get(error_type, 0) + 1
                        
                except json.JSONDecodeError:
                    failure_record['error_message'] = 'Failed to parse error details'
                    failure_record['error_type'] = 'ParseError'
                
                failure_info['failed_records'].append(failure_record)
        
        elif 'errorMessage' in event:
            # Direct Lambda error
            failure_record = {
                'record_id': context.aws_request_id if context else 'unknown',
                'error_message': event['errorMessage'],
                'error_type': event.get('errorType', 'Unknown'),
                'stack_trace': event.get('trace', [])
            }
            
            failure_info['failed_records'].append(failure_record)
            error_type = failure_record['error_type']
            failure_info['error_types'][error_type] = 1
        
        else:
            # Generic event
            failure_record = {
                'record_id': 'unknown',
                'error_message': 'Unknown failure type',
                'error_type': 'Unknown',
                'raw_event': json.dumps(event)
            }
            
            failure_info['failed_records'].append(failure_record)
            failure_info['error_types']['Unknown'] = 1
        
        failure_info['total_failures'] = len(failure_info['failed_records'])
        
    except Exception as e:
        logger.error(f"Error extracting failure info: {str(e)}")
        failure_info['extraction_error'] = str(e)
    
    return failure_info

def publish_failure_metrics(failure_info):
    """Publish failure metrics to CloudWatch"""
    try:
        metric_data = []
        
        # Total failure count
        metric_data.append({
            'MetricName': 'DeadLetterQueueEvents',
            'Value': failure_info['total_failures'],
            'Unit': 'Count',
            'Dimensions': [
                {
                    'Name': 'SourceFunction',
                    'Value': SOURCE_FUNCTION
                }
            ],
            'Timestamp': datetime.utcnow()
        })
        
        # Error type breakdown
        for error_type, count in failure_info.get('error_types', {}).items():
            metric_data.append({
                'MetricName': 'DeadLetterQueueEventsByType',
                'Value': count,
                'Unit': 'Count',
                'Dimensions': [
                    {
                        'Name': 'SourceFunction',
                        'Value': SOURCE_FUNCTION
                    },
                    {
                        'Name': 'ErrorType',
                        'Value': error_type
                    }
                ],
                'Timestamp': datetime.utcnow()
            })
        
        # Publish metrics
        cloudwatch.put_metric_data(
            Namespace='MultiAccountAnomalyDetection/DeadLetterQueue',
            MetricData=metric_data
        )
        
        logger.info(f"Published {len(metric_data)} failure metrics to CloudWatch")
        
    except Exception as e:
        logger.error(f"Error publishing failure metrics: {str(e)}")

def send_failure_alert(failure_info):
    """Send failure alert via SNS"""
    try:
        if not SNS_TOPIC_ARN:
            logger.warning("No SNS topic configured for failure alerts")
            return
        
        # Create alert message
        message = f"DEAD LETTER QUEUE ALERT\n"
        message += f"{'=' * 50}\n\n"
        message += f"Source Function: {SOURCE_FUNCTION}\n"
        message += f"Timestamp: {failure_info['timestamp']}\n"
        message += f"Total Failed Records: {failure_info['total_failures']}\n\n"
        
        # Error type breakdown
        if failure_info.get('error_types'):
            message += "Error Types:\n"
            for error_type, count in failure_info['error_types'].items():
                message += f"  • {error_type}: {count} occurrences\n"
            message += "\n"
        
        # Sample error details (first few records)
        if failure_info.get('failed_records'):
            message += "Sample Error Details:\n"
            for i, record in enumerate(failure_info['failed_records'][:3]):  # Show first 3
                message += f"\nRecord {i+1}:\n"
                message += f"  ID: {record.get('record_id', 'unknown')}\n"
                message += f"  Error Type: {record.get('error_type', 'Unknown')}\n"
                message += f"  Error Message: {record.get('error_message', 'No message')}\n"
                
                if len(failure_info['failed_records']) > 3:
                    message += f"\n... and {len(failure_info['failed_records']) - 3} more records\n"
        
        message += f"\n{'=' * 50}\n"
        message += "This alert indicates that some events could not be processed successfully.\n"
        message += "Please check the Lambda function logs for detailed error information.\n"
        
        # Send alert
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"Dead Letter Queue Alert - {SOURCE_FUNCTION}",
            Message=message
        )
        
        logger.info(f"Sent failure alert via SNS: {response['MessageId']}")
        
    except Exception as e:
        logger.error(f"Error sending failure alert: {str(e)}")

def log_failure_details(failure_info):
    """Log detailed failure information for debugging"""
    try:
        logger.error(f"=== DEAD LETTER QUEUE FAILURE DETAILS ===")
        logger.error(f"Source Function: {SOURCE_FUNCTION}")
        logger.error(f"Timestamp: {failure_info['timestamp']}")
        logger.error(f"Total Failures: {failure_info['total_failures']}")
        
        # Log error type summary
        if failure_info.get('error_types'):
            logger.error("Error Type Summary:")
            for error_type, count in failure_info['error_types'].items():
                logger.error(f"  {error_type}: {count}")
        
        # Log individual failure details
        for i, record in enumerate(failure_info.get('failed_records', [])):
            logger.error(f"Failed Record {i+1}:")
            logger.error(f"  ID: {record.get('record_id', 'unknown')}")
            logger.error(f"  Error Type: {record.get('error_type', 'Unknown')}")
            logger.error(f"  Error Message: {record.get('error_message', 'No message')}")
            
            # Log stack trace if available
            if record.get('stack_trace'):
                logger.error(f"  Stack Trace: {record['stack_trace']}")
            
            # Log raw body for debugging (truncated)
            if record.get('body'):
                body = record['body'][:500] + '...' if len(record['body']) > 500 else record['body']
                logger.error(f"  Body: {body}")
        
        logger.error("=== END FAILURE DETAILS ===")
        
    except Exception as e:
        logger.error(f"Error logging failure details: {str(e)}")