from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_logs as logs,
    aws_lambda as _lambda,
)
from constructs import Construct
from typing import List, Optional


class MonitoringStack(Stack):
    """
    Stack for comprehensive monitoring and alerting of the multi-account
    anomaly detection system.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        lambda_functions: List[_lambda.Function] = None,
        opensearch_domain = None,
        sns_topic: sns.Topic = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.lambda_functions = lambda_functions or []
        self.opensearch_domain = opensearch_domain
        self.sns_topic = sns_topic

        # Create monitoring dashboard
        self.create_system_dashboard()
        
        # Create CloudWatch alarms
        self.create_lambda_alarms()
        self.create_opensearch_alarms()
        self.create_system_health_alarms()

    def create_system_dashboard(self):
        """Create comprehensive system monitoring dashboard"""
        
        dashboard = cloudwatch.Dashboard(
            self,
            "AnomalyDetectionSystemDashboard",
            dashboard_name="Multi-Account-Anomaly-Detection-System",
            period_override=cloudwatch.PeriodOverride.AUTO,
        )

        # Lambda Functions Performance Section
        lambda_widgets = []
        for func in self.lambda_functions:
            lambda_widgets.extend([
                cloudwatch.GraphWidget(
                    title=f"{func.function_name} - Invocations & Errors",
                    left=[
                        cloudwatch.Metric(
                            namespace="AWS/Lambda",
                            metric_name="Invocations",
                            dimensions_map={"FunctionName": func.function_name},
                            statistic="Sum"
                        )
                    ],
                    right=[
                        cloudwatch.Metric(
                            namespace="AWS/Lambda",
                            metric_name="Errors",
                            dimensions_map={"FunctionName": func.function_name},
                            statistic="Sum"
                        )
                    ],
                    width=12,
                    height=6
                ),
                cloudwatch.GraphWidget(
                    title=f"{func.function_name} - Duration & Throttles",
                    left=[
                        cloudwatch.Metric(
                            namespace="AWS/Lambda",
                            metric_name="Duration",
                            dimensions_map={"FunctionName": func.function_name},
                            statistic="Average"
                        )
                    ],
                    right=[
                        cloudwatch.Metric(
                            namespace="AWS/Lambda",
                            metric_name="Throttles",
                            dimensions_map={"FunctionName": func.function_name},
                            statistic="Sum"
                        )
                    ],
                    width=12,
                    height=6
                )
            ])

        # OpenSearch Performance Section
        opensearch_widgets = []
        if self.opensearch_domain:
            opensearch_widgets = [
                cloudwatch.GraphWidget(
                    title="OpenSearch - Cluster Health",
                    left=[
                        cloudwatch.Metric(
                            namespace="AWS/ES",
                            metric_name="ClusterStatus.yellow",
                            dimensions_map={"DomainName": self.opensearch_domain.domain_name, "ClientId": self.account},
                            statistic="Maximum"
                        ),
                        cloudwatch.Metric(
                            namespace="AWS/ES",
                            metric_name="ClusterStatus.red",
                            dimensions_map={"DomainName": self.opensearch_domain.domain_name, "ClientId": self.account},
                            statistic="Maximum"
                        )
                    ],
                    width=12,
                    height=6
                ),
                cloudwatch.GraphWidget(
                    title="OpenSearch - Search & Indexing",
                    left=[
                        cloudwatch.Metric(
                            namespace="AWS/ES",
                            metric_name="SearchRate",
                            dimensions_map={"DomainName": self.opensearch_domain.domain_name, "ClientId": self.account},
                            statistic="Average"
                        )
                    ],
                    right=[
                        cloudwatch.Metric(
                            namespace="AWS/ES",
                            metric_name="IndexingRate",
                            dimensions_map={"DomainName": self.opensearch_domain.domain_name, "ClientId": self.account},
                            statistic="Average"
                        )
                    ],
                    width=12,
                    height=6
                )
            ]

        # System Health Overview
        system_widgets = [
            cloudwatch.SingleValueWidget(
                title="System Health Overview",
                metrics=[
                    cloudwatch.Metric(
                        namespace="AWS/Lambda",
                        metric_name="Invocations",
                        dimensions_map={"FunctionName": func.function_name},
                        statistic="Sum"
                    ) for func in self.lambda_functions
                ],
                width=24,
                height=6
            )
        ]

        # Add all widgets to dashboard
        dashboard.add_widgets(*system_widgets)
        dashboard.add_widgets(*lambda_widgets)
        dashboard.add_widgets(*opensearch_widgets)

        # Store reference
        self.dashboard = dashboard

    def create_lambda_alarms(self):
        """Create CloudWatch alarms for Lambda functions"""
        
        self.lambda_alarms = []
        
        for func in self.lambda_functions:
            # Error rate alarm
            error_alarm = cloudwatch.Alarm(
                self,
                f"{func.function_name}ErrorAlarm",
                alarm_name=f"{func.function_name}-HighErrorRate",
                alarm_description=f"High error rate detected for {func.function_name}",
                metric=cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Errors",
                    dimensions_map={"FunctionName": func.function_name},
                    statistic="Sum",
                    period=Duration.minutes(5)
                ),
                threshold=5,
                evaluation_periods=2,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
            )
            
            # Duration alarm
            duration_alarm = cloudwatch.Alarm(
                self,
                f"{func.function_name}DurationAlarm",
                alarm_name=f"{func.function_name}-HighDuration",
                alarm_description=f"High duration detected for {func.function_name}",
                metric=cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Duration",
                    dimensions_map={"FunctionName": func.function_name},
                    statistic="Average",
                    period=Duration.minutes(5)
                ),
                threshold=30000,  # 30 seconds
                evaluation_periods=3,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
            )
            
            # Throttle alarm
            throttle_alarm = cloudwatch.Alarm(
                self,
                f"{func.function_name}ThrottleAlarm",
                alarm_name=f"{func.function_name}-Throttles",
                alarm_description=f"Throttles detected for {func.function_name}",
                metric=cloudwatch.Metric(
                    namespace="AWS/Lambda",
                    metric_name="Throttles",
                    dimensions_map={"FunctionName": func.function_name},
                    statistic="Sum",
                    period=Duration.minutes(5)
                ),
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD
            )
            
            # Add SNS actions if topic provided
            if self.sns_topic:
                error_alarm.add_alarm_action(cw_actions.SnsAction(self.sns_topic))
                duration_alarm.add_alarm_action(cw_actions.SnsAction(self.sns_topic))
                throttle_alarm.add_alarm_action(cw_actions.SnsAction(self.sns_topic))
            
            self.lambda_alarms.extend([error_alarm, duration_alarm, throttle_alarm])

    def create_opensearch_alarms(self):
        """Create CloudWatch alarms for OpenSearch domain"""
        
        if not self.opensearch_domain:
            return
            
        self.opensearch_alarms = []
        
        # Cluster status alarm
        cluster_status_alarm = cloudwatch.Alarm(
            self,
            "OpenSearchClusterStatusAlarm",
            alarm_name="OpenSearch-ClusterStatus-Red",
            alarm_description="OpenSearch cluster status is red",
            metric=cloudwatch.Metric(
                namespace="AWS/ES",
                metric_name="ClusterStatus.red",
                dimensions_map={
                    "DomainName": self.opensearch_domain.domain_name,
                    "ClientId": self.account
                },
                statistic="Maximum",
                period=Duration.minutes(1)
            ),
            threshold=0,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        
        # Storage utilization alarm
        storage_alarm = cloudwatch.Alarm(
            self,
            "OpenSearchStorageAlarm",
            alarm_name="OpenSearch-HighStorageUtilization",
            alarm_description="OpenSearch storage utilization is high",
            metric=cloudwatch.Metric(
                namespace="AWS/ES",
                metric_name="StorageUtilization",
                dimensions_map={
                    "DomainName": self.opensearch_domain.domain_name,
                    "ClientId": self.account
                },
                statistic="Maximum",
                period=Duration.minutes(5)
            ),
            threshold=85,  # 85% utilization
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        
        # CPU utilization alarm
        cpu_alarm = cloudwatch.Alarm(
            self,
            "OpenSearchCPUAlarm",
            alarm_name="OpenSearch-HighCPUUtilization",
            alarm_description="OpenSearch CPU utilization is high",
            metric=cloudwatch.Metric(
                namespace="AWS/ES",
                metric_name="CPUUtilization",
                dimensions_map={
                    "DomainName": self.opensearch_domain.domain_name,
                    "ClientId": self.account
                },
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=80,  # 80% CPU
            evaluation_periods=3,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        
        # Add SNS actions if topic provided
        if self.sns_topic:
            cluster_status_alarm.add_alarm_action(cw_actions.SnsAction(self.sns_topic))
            storage_alarm.add_alarm_action(cw_actions.SnsAction(self.sns_topic))
            cpu_alarm.add_alarm_action(cw_actions.SnsAction(self.sns_topic))
        
        self.opensearch_alarms = [cluster_status_alarm, storage_alarm, cpu_alarm]

    def create_system_health_alarms(self):
        """Create composite alarms for overall system health"""
        
        if not self.lambda_alarms and not self.opensearch_alarms:
            return
        
        # Create composite alarm for system health
        all_alarms = []
        if hasattr(self, 'lambda_alarms'):
            all_alarms.extend(self.lambda_alarms)
        if hasattr(self, 'opensearch_alarms'):
            all_alarms.extend(self.opensearch_alarms)
        
        if all_alarms:
            system_health_alarm = cloudwatch.CompositeAlarm(
                self,
                "SystemHealthAlarm",
                alarm_name="AnomalyDetectionSystem-OverallHealth",
                alarm_description="Overall health of the anomaly detection system",
                composite_alarm_rule=cloudwatch.AlarmRule.any_of(*[
                    cloudwatch.AlarmRule.from_alarm(alarm, cloudwatch.AlarmState.ALARM)
                    for alarm in all_alarms[:10]  # Limit to 10 alarms due to AWS limits
                ])
            )
            
            if self.sns_topic:
                system_health_alarm.add_alarm_action(cw_actions.SnsAction(self.sns_topic))
            
            self.system_health_alarm = system_health_alarm

        # Outputs
        CfnOutput(
            self,
            "DashboardURL",
            value=f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={self.dashboard.dashboard_name}",
            description="CloudWatch Dashboard URL for system monitoring"
        )
        
        CfnOutput(
            self,
            "MonitoringStatus",
            value="Comprehensive monitoring and alerting configured",
            description="Monitoring system status"
        )