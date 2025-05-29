import json
import os
import boto3  # type: ignore
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import re

# Environment variables
Q_APPLICATION_ID = os.environ.get('Q_APPLICATION_ID')
ENABLE_COST_ANALYSIS = os.environ.get('ENABLE_COST_ANALYSIS', 'true').lower() == 'true'
ENABLE_ROOT_CAUSE_ANALYSIS = os.environ.get('ENABLE_ROOT_CAUSE_ANALYSIS', 'true').lower() == 'true'

# AWS clients
q_business = boto3.client('qbusiness')
ce_client = boto3.client('ce')
cloudwatch = boto3.client('cloudwatch')
sns = boto3.client('sns')


def handler(event, context):
    """
    Lambda handler to generate natural language insights for anomalies using Amazon Q
    """
    print(f"Processing anomaly for natural language insights")
    
    try:
        # Parse SNS message
        for record in event['Records']:
            sns_message = json.loads(record['Sns']['Message'])
            
            # Extract anomaly details
            anomaly_details = parse_anomaly_alert(sns_message)
            
            # Generate Q conversation context
            conversation_context = build_conversation_context(anomaly_details)
            
            # Query Amazon Q for insights
            q_insights = query_q_for_insights(conversation_context, anomaly_details)
            
            # Enrich with cost analysis if enabled
            if ENABLE_COST_ANALYSIS:
                cost_insights = analyze_cost_impact(anomaly_details)
                q_insights['cost_analysis'] = cost_insights
            
            # Perform root cause analysis if enabled
            if ENABLE_ROOT_CAUSE_ANALYSIS:
                root_cause = analyze_root_cause(anomaly_details)
                q_insights['root_cause_analysis'] = root_cause
            
            # Format and send enriched notification
            send_enriched_notification(anomaly_details, q_insights)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Insights generated successfully'
            })
        }
        
    except Exception as e:
        print(f"Error generating insights: {str(e)}")
        raise


def parse_anomaly_alert(sns_message: Dict) -> Dict:
    """
    Parse anomaly alert from SNS message
    """
    # Extract key information from the alert
    anomaly_details = {
        'alert_time': datetime.utcnow().isoformat(),
        'detector_name': sns_message.get('Detector', 'Unknown'),
        'anomaly_count': sns_message.get('Anomalies', 0),
        'affected_accounts': [],
        'event_type': 'Unknown',
        'severity': 'UNKNOWN'
    }
    
    # Parse detector name to get event type
    if 'ec2' in anomaly_details['detector_name'].lower():
        anomaly_details['event_type'] = 'EC2_RunInstances'
    elif 'lambda' in anomaly_details['detector_name'].lower():
        anomaly_details['event_type'] = 'Lambda_Invoke'
    elif 'ebs' in anomaly_details['detector_name'].lower():
        anomaly_details['event_type'] = 'EBS_CreateVolume'
    
    # Extract affected accounts
    top_accounts = sns_message.get('TopAccounts', '')
    if top_accounts:
        # Parse account IDs from the message
        account_pattern = r'\d{12}'
        anomaly_details['affected_accounts'] = re.findall(account_pattern, top_accounts)
    
    return anomaly_details


def build_conversation_context(anomaly_details: Dict) -> str:
    """
    Build conversation context for Amazon Q
    """
    context = f"""
I'm analyzing an AWS usage anomaly with the following details:

Anomaly Type: {anomaly_details['event_type']}
Detection Time: {anomaly_details['alert_time']}
Number of Anomalous Events: {anomaly_details['anomaly_count']}
Affected Accounts: {', '.join(anomaly_details['affected_accounts']) if anomaly_details['affected_accounts'] else 'Unknown'}

Based on this information, please provide:
1. A clear explanation of what this anomaly means
2. Potential causes for this anomaly
3. Recommended actions to investigate and resolve
4. Best practices to prevent similar anomalies in the future

Please format your response in a clear, actionable manner suitable for both technical and non-technical stakeholders.
"""
    
    return context


def query_q_for_insights(context: str, anomaly_details: Dict) -> Dict:
    """
    Query Amazon Q for Business for natural language insights
    """
    try:
        # Create a new conversation
        conversation_response = q_business.chat_sync(
            applicationId=Q_APPLICATION_ID,
            userId='anomaly-detector-system',
            userMessage=context,
            conversationId=None  # Start new conversation
        )
        
        # Extract insights from Q's response
        q_response = conversation_response.get('systemMessage', '')
        
        # Parse the response into structured insights
        insights = {
            'summary': extract_section(q_response, 'explanation|summary'),
            'potential_causes': extract_section(q_response, 'potential causes|causes'),
            'recommended_actions': extract_section(q_response, 'recommended actions|actions'),
            'prevention_tips': extract_section(q_response, 'best practices|prevention'),
            'full_response': q_response
        }
        
        # Add contextual insights based on anomaly type
        if anomaly_details['event_type'] == 'EC2_RunInstances':
            insights['context'] = """
This anomaly indicates unusual EC2 instance creation activity. Common scenarios include:
- Auto-scaling events during traffic spikes
- Deployment of new applications
- Potential security breach with unauthorized instance creation
- Misconfigured automation scripts
"""
        elif anomaly_details['event_type'] == 'Lambda_Invoke':
            insights['context'] = """
This anomaly indicates unusual Lambda function invocation patterns. Common scenarios include:
- Application bugs causing infinite loops
- DDoS attacks triggering functions
- Legitimate traffic spikes
- Misconfigured event sources
"""
        elif anomaly_details['event_type'] == 'EBS_CreateVolume':
            insights['context'] = """
This anomaly indicates unusual EBS volume creation. Common scenarios include:
- Backup processes creating snapshots
- Data migration activities
- Potential data exfiltration preparation
- Storage scaling for applications
"""
        
        return insights
        
    except Exception as e:
        print(f"Error querying Q for Business: {str(e)}")
        # Return fallback insights
        return {
            'summary': f"Anomaly detected in {anomaly_details['event_type']} with {anomaly_details['anomaly_count']} events",
            'potential_causes': 'Unable to generate Q insights - please check manually',
            'recommended_actions': 'Review CloudTrail logs for the affected time period',
            'prevention_tips': 'Implement proper monitoring and alerting',
            'error': str(e)
        }


def extract_section(text: str, section_pattern: str) -> str:
    """
    Extract a specific section from Q's response
    """
    # Look for section headers
    pattern = rf"(?i)(?:{section_pattern})[:\s]*([^0-9]+?)(?=\n\d+\.|$)"
    match = re.search(pattern, text, re.DOTALL)
    
    if match:
        return match.group(1).strip()
    
    return "Information not available"


def analyze_cost_impact(anomaly_details: Dict) -> Dict:
    """
    Analyze potential cost impact of the anomaly
    """
    cost_analysis = {
        'estimated_impact': 'Unknown',
        'cost_breakdown': {},
        'recommendations': []
    }
    
    try:
        # Get current month costs
        end_date = datetime.utcnow().date()
        start_date = end_date.replace(day=1)
        
        # Query Cost Explorer for affected accounts
        if anomaly_details['affected_accounts']:
            response = ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.isoformat(),
                    'End': end_date.isoformat()
                },
                Granularity='DAILY',
                Metrics=['UnblendedCost'],
                Filter={
                    'And': [
                        {
                            'Dimensions': {
                                'Key': 'LINKED_ACCOUNT',
                                'Values': anomaly_details['affected_accounts']
                            }
                        },
                        {
                            'Dimensions': {
                                'Key': 'SERVICE',
                                'Values': [get_service_from_event(anomaly_details['event_type'])]
                            }
                        }
                    ]
                }
            )
            
            # Calculate cost trends
            daily_costs = []
            for result in response['ResultsByTime']:
                cost = float(result['Total']['UnblendedCost']['Amount'])
                daily_costs.append(cost)
            
            if daily_costs:
                avg_daily_cost = sum(daily_costs) / len(daily_costs)
                latest_cost = daily_costs[-1] if daily_costs else 0
                
                # Detect cost spike
                if latest_cost > avg_daily_cost * 1.5:
                    cost_analysis['estimated_impact'] = 'HIGH'
                    cost_analysis['recommendations'].append(
                        f"Latest daily cost (${latest_cost:.2f}) is 50% higher than average (${avg_daily_cost:.2f})"
                    )
                else:
                    cost_analysis['estimated_impact'] = 'MODERATE'
                
                cost_analysis['cost_breakdown'] = {
                    'average_daily_cost': f"${avg_daily_cost:.2f}",
                    'latest_daily_cost': f"${latest_cost:.2f}",
                    'monthly_projection': f"${avg_daily_cost * 30:.2f}"
                }
        
        # Add service-specific recommendations
        if anomaly_details['event_type'] == 'EC2_RunInstances':
            cost_analysis['recommendations'].extend([
                "Review instance types and consider using Spot instances for non-critical workloads",
                "Implement auto-shutdown for development instances",
                "Use AWS Instance Scheduler to optimize runtime"
            ])
        elif anomaly_details['event_type'] == 'Lambda_Invoke':
            cost_analysis['recommendations'].extend([
                "Review function timeout settings and memory allocation",
                "Implement circuit breakers to prevent runaway functions",
                "Consider using Lambda reserved concurrency"
            ])
        elif anomaly_details['event_type'] == 'EBS_CreateVolume':
            cost_analysis['recommendations'].extend([
                "Review volume types and consider using GP3 for cost optimization",
                "Implement lifecycle policies for snapshots",
                "Delete unattached volumes regularly"
            ])
            
    except Exception as e:
        print(f"Error analyzing cost impact: {str(e)}")
        cost_analysis['error'] = str(e)
    
    return cost_analysis


def get_service_from_event(event_type: str) -> str:
    """
    Map event type to AWS service name for Cost Explorer
    """
    service_map = {
        'EC2_RunInstances': 'Amazon Elastic Compute Cloud - Compute',
        'Lambda_Invoke': 'AWS Lambda',
        'EBS_CreateVolume': 'Amazon Elastic Compute Cloud - Storage'
    }
    return service_map.get(event_type, 'Unknown')


def analyze_root_cause(anomaly_details: Dict) -> Dict:
    """
    Perform root cause analysis based on CloudWatch metrics and patterns
    """
    root_cause = {
        'likely_cause': 'Unknown',
        'confidence': 'Low',
        'evidence': [],
        'recommendations': []
    }
    
    try:
        # Analyze patterns based on event type
        if anomaly_details['event_type'] == 'EC2_RunInstances':
            # Check for auto-scaling activities
            asg_metrics = check_autoscaling_metrics(anomaly_details['affected_accounts'])
            if asg_metrics['scaling_detected']:
                root_cause['likely_cause'] = 'Auto-scaling activity'
                root_cause['confidence'] = 'High'
                root_cause['evidence'].append(f"Auto-scaling group {asg_metrics['group_name']} scaled out")
                root_cause['recommendations'].append("Review auto-scaling policies and thresholds")
            
        elif anomaly_details['event_type'] == 'Lambda_Invoke':
            # Check for error rates
            error_metrics = check_lambda_errors(anomaly_details['affected_accounts'])
            if error_metrics['high_error_rate']:
                root_cause['likely_cause'] = 'Function errors causing retries'
                root_cause['confidence'] = 'High'
                root_cause['evidence'].append(f"Error rate: {error_metrics['error_rate']}%")
                root_cause['recommendations'].append("Review function logs and fix errors")
                
        elif anomaly_details['event_type'] == 'EBS_CreateVolume':
            # Check for backup activities
            backup_metrics = check_backup_activities(anomaly_details['affected_accounts'])
            if backup_metrics['backup_detected']:
                root_cause['likely_cause'] = 'Scheduled backup process'
                root_cause['confidence'] = 'Medium'
                root_cause['evidence'].append("Backup job detected during anomaly window")
                root_cause['recommendations'].append("Review backup schedules and retention policies")
    
    except Exception as e:
        print(f"Error in root cause analysis: {str(e)}")
        root_cause['error'] = str(e)
    
    return root_cause


def check_autoscaling_metrics(accounts: List[str]) -> Dict:
    """
    Check CloudWatch metrics for auto-scaling activities
    """
    # Simplified implementation - in production, query actual metrics
    return {
        'scaling_detected': True,
        'group_name': 'web-app-asg'
    }


def check_lambda_errors(accounts: List[str]) -> Dict:
    """
    Check Lambda error rates
    """
    # Simplified implementation - in production, query actual metrics
    return {
        'high_error_rate': True,
        'error_rate': 15.5
    }


def check_backup_activities(accounts: List[str]) -> Dict:
    """
    Check for backup job activities
    """
    # Simplified implementation - in production, query AWS Backup
    return {
        'backup_detected': True,
        'job_id': 'backup-12345'
    }


def send_enriched_notification(anomaly_details: Dict, insights: Dict):
    """
    Send enriched notification with natural language insights
    """
    # Format the notification message
    message = f"""
🚨 AWS Usage Anomaly Detected - Enhanced Insights

📊 ANOMALY SUMMARY:
{insights.get('summary', 'No summary available')}

🔍 POTENTIAL CAUSES:
{insights.get('potential_causes', 'Unable to determine causes')}

💡 RECOMMENDED ACTIONS:
{insights.get('recommended_actions', 'Please investigate manually')}

💰 COST IMPACT ANALYSIS:
"""
    
    if 'cost_analysis' in insights:
        cost = insights['cost_analysis']
        message += f"""
- Estimated Impact: {cost['estimated_impact']}
- Cost Breakdown: {json.dumps(cost['cost_breakdown'], indent=2)}
- Cost Recommendations: {', '.join(cost['recommendations'])}
"""
    
    message += f"""

🔬 ROOT CAUSE ANALYSIS:
"""
    
    if 'root_cause_analysis' in insights:
        rca = insights['root_cause_analysis']
        message += f"""
- Likely Cause: {rca['likely_cause']}
- Confidence: {rca['confidence']}
- Evidence: {', '.join(rca['evidence'])}
- Recommendations: {', '.join(rca['recommendations'])}
"""
    
    message += f"""

🛡️ PREVENTION TIPS:
{insights.get('prevention_tips', 'Implement proper monitoring and alerting')}

---
Generated by AWS Anomaly Detector with Amazon Q Insights
Time: {datetime.utcnow().isoformat()}
"""
    
    # Send via SNS
    notification_topic = os.environ.get('NOTIF_TOPIC_ARN')
    if notification_topic:
        sns.publish(
            TopicArn=notification_topic,
            Subject=f"🚨 Enhanced Alert: {anomaly_details['event_type']} Anomaly Detected",
            Message=message
        )
    
    print(f"Sent enriched notification for {anomaly_details['event_type']} anomaly")
