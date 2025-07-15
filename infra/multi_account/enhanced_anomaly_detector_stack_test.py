from os import path
from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    CustomResource,
    aws_opensearchservice as opensearch,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_logs_destinations as destinations,
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
    aws_cloudwatch_actions as cw_actions,
    aws_events as events,
    aws_events_targets as targets,
    custom_resources as cr,
)
from constructs import Construct

PWD = path.dirname(path.realpath(__file__))
LAMBDA_DIR = path.join(PWD, "..", "..", "lambdas")
SHARED_DIR = path.join(PWD, "..", "..", "shared")


class EnhancedAnomalyDetectorStack(Stack):
    """
    Enhanced anomaly detector stack with multi-account support.
    Q Business integration disabled for CDK compatibility.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        log_group: logs.LogGroup,
        opensearch_domain: opensearch.Domain,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Enhanced CloudWatch to OpenSearch Lambda for multi-account support
        multi_account_logs_lambda_role = iam.Role(
            self,
            "MultiAccountLogsLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for multi-account CloudWatch logs to OpenSearch",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Add OpenSearch permissions if domain is provided
        if opensearch_domain:
            multi_account_logs_lambda_role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "es:ESHttpPost",
                        "es:ESHttpPut",
                        "es:ESHttpGet",
                        "es:ESHttpPatch",
                    ],
                    resources=[f"{opensearch_domain.domain_arn}/*"],
                )
            )

        # Enhanced logs processing function with account awareness
        multi_account_logs_function = _lambda.Function(
            self,
            "MultiAccountLogsFunction",
            description="Enhanced CloudWatch logs to OpenSearch with multi-account support",
            code=_lambda.Code.from_asset(
                path.join(LAMBDA_DIR, "CrossAccountAnomalyProcessor")
            ),
            handler="index.handler",
            runtime=_lambda.Runtime.NODEJS_18_X,
            timeout=Duration.seconds(300),
            memory_size=512,
            role=multi_account_logs_lambda_role,
            environment={
                "OPENSEARCH_DOMAIN_ENDPOINT": opensearch_domain.domain_endpoint if opensearch_domain else "",
                "ENABLE_ACCOUNT_ENRICHMENT": "true",
                "ENABLE_ORG_CONTEXT": "true",
            },
        )

        # Create subscription filter for organization logs
        logs.SubscriptionFilter(
            self,
            "MultiAccountLogsSubscription",
            log_group=log_group,
            destination=destinations.LambdaDestination(multi_account_logs_function),
            filter_pattern=logs.FilterPattern.all_events(),
        )

        # Cross-account anomaly configuration Lambda
        cross_account_config_function = _lambda.Function(
            self,
            "CrossAccountConfigFunction",
            description="Configure OpenSearch for cross-account anomaly detection",
            code=_lambda.Code.from_asset(
                path.join(LAMBDA_DIR, "CrossAccountAnomalyProcessor")
            ),
            handler="config.handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            timeout=Duration.seconds(600),
            environment={
                "OPENSEARCH_HOST": opensearch_domain.domain_endpoint if opensearch_domain else "",
                "ENABLE_MULTI_ACCOUNT": "true",
            },
        )

        # Add OpenSearch admin permissions if domain is provided
        if opensearch_domain:
            cross_account_config_function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["es:ESHttp*"],
                    resources=[f"{opensearch_domain.domain_arn}/*"],
                )
            )

        # Add organizations read permissions
        cross_account_config_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "organizations:ListAccounts",
                    "organizations:ListOrganizationalUnitsForParent",
                    "organizations:DescribeOrganization",
                    "organizations:DescribeAccount",
                ],
                resources=["*"],
            )
        )

        # Create custom resource to configure multi-account anomaly detectors
        config_provider = cr.Provider(
            self,
            "CrossAccountConfigProvider",
            on_event_handler=cross_account_config_function,
            log_retention=logs.RetentionDays.ONE_DAY,
        )

        CustomResource(
            self,
            "CrossAccountAnomalyConfig",
            service_token=config_provider.service_token,
            properties={
                "action": "configure_multi_account_detectors",
                "detectors": [
                    {
                        "name": "multi-account-ec2-run-instances",
                        "category_fields": ["recipientAccountId", "awsRegion"],
                    },
                    {
                        "name": "multi-account-lambda-invoke",
                        "category_fields": [
                            "recipientAccountId",
                            "requestParameters.functionName.keyword",
                        ],
                    },
                    {
                        "name": "multi-account-ebs-create-volume",
                        "category_fields": ["recipientAccountId", "awsRegion"],
                    },
                ],
            },
        )

        # Q Business connector function for natural language insights
        q_connector_role = iam.Role(
            self,
            "QBusinessConnectorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Q Business connector Lambda",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Add permissions for Q Business connector with least privilege
        if opensearch_domain:
            q_connector_role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "es:ESHttpGet",
                        "es:ESHttpPost",
                    ],
                    resources=[f"{opensearch_domain.domain_arn}/*"],
                )
            )

        q_connector_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "qbusiness:PutDocument",
                    "qbusiness:DeleteDocument",
                    "qbusiness:BatchPutDocument",
                    "qbusiness:BatchDeleteDocument",
                ],
                resources=["*"],  # Will be restricted by Q Business stack
            )
        )

        q_connector_function = _lambda.Function(
            self,
            "QBusinessConnectorFunction",
            description="Sync OpenSearch anomalies to Q Business",
            code=_lambda.Code.from_asset(
                path.join(LAMBDA_DIR, "QBusinessConnector")
            ),
            handler="main.handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            timeout=Duration.seconds(600),
            memory_size=1024,
            role=q_connector_role,
            environment={
                "OPENSEARCH_ENDPOINT": opensearch_domain.domain_endpoint if opensearch_domain else "",
                "ENABLE_INSIGHTS": "true",
            },
        )

        # Natural language insights function
        nl_insights_function = _lambda.Function(
            self,
            "NaturalLanguageInsightsFunction",
            description="Generate natural language insights for anomalies",
            code=_lambda.Code.from_asset(
                path.join(LAMBDA_DIR, "QBusinessConnector")
            ),
            handler="insights.handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            timeout=Duration.seconds(300),
            memory_size=512,
            environment={
                "ENABLE_COST_ANALYSIS": "true",
                "ENABLE_RECOMMENDATIONS": "true",
            },
        )

        # === MONITORING AND ALERTING COMPONENTS ===
        
        # Create SNS topic for system alerts
        system_alerts_topic = sns.Topic(
            self,
            "SystemAlertsTopic",
            display_name="Multi-Account Anomaly Detection System Alerts",
            topic_name="multi-account-anomaly-system-alerts"
        )

        # Create CloudWatch Dashboard for system monitoring
        dashboard = cloudwatch.Dashboard(
            self,
            "MultiAccountAnomalyDashboard",
            dashboard_name="MultiAccountAnomalyDetection",
            widgets=[
                [
                    # Lambda function metrics
                    cloudwatch.GraphWidget(
                        title="Lambda Function Performance",
                        left=[
                            multi_account_logs_function.metric_duration(statistic="Average"),
                            cross_account_config_function.metric_duration(statistic="Average"),
                            q_connector_function.metric_duration(statistic="Average"),
                        ],
                        right=[
                            multi_account_logs_function.metric_invocations(),
                            cross_account_config_function.metric_invocations(),
                            q_connector_function.metric_invocations(),
                        ],
                        width=12,
                        height=6
                    )
                ],
                [
                    # Error rates
                    cloudwatch.GraphWidget(
                        title="Lambda Function Errors",
                        left=[
                            multi_account_logs_function.metric_errors(),
                            cross_account_config_function.metric_errors(),
                            q_connector_function.metric_errors(),
                        ],
                        width=6,
                        height=6
                    ),
                    # Throttles
                    cloudwatch.GraphWidget(
                        title="Lambda Function Throttles",
                        left=[
                            multi_account_logs_function.metric_throttles(),
                            cross_account_config_function.metric_throttles(),
                            q_connector_function.metric_throttles(),
                        ],
                        width=6,
                        height=6
                    )
                ]
            ]
        )

        # Create custom metrics for anomaly detection accuracy
        anomaly_accuracy_metric = cloudwatch.Metric(
            namespace="MultiAccountAnomalyDetection",
            metric_name="AnomalyDetectionAccuracy",
            statistic="Average"
        )

        processing_success_metric = cloudwatch.Metric(
            namespace="MultiAccountAnomalyDetection", 
            metric_name="ProcessingSuccessRate",
            statistic="Average"
        )

        # Create alarms for Lambda function errors
        multi_account_logs_error_alarm = cloudwatch.Alarm(
            self,
            "MultiAccountLogsErrorAlarm",
            metric=multi_account_logs_function.metric_errors(period=Duration.minutes(5)),
            threshold=5,
            evaluation_periods=2,
            alarm_description="Multi-account logs processing function error rate is high",
            alarm_name="MultiAccountLogs-HighErrorRate"
        )

        multi_account_logs_error_alarm.add_alarm_action(
            cw_actions.SnsAction(system_alerts_topic)
        )

        # Create alarm for Q Business connector errors
        q_connector_error_alarm = cloudwatch.Alarm(
            self,
            "QConnectorErrorAlarm",
            metric=q_connector_function.metric_errors(period=Duration.minutes(5)),
            threshold=3,
            evaluation_periods=2,
            alarm_description="Q Business connector function error rate is high",
            alarm_name="QBusinessConnector-HighErrorRate"
        )

        q_connector_error_alarm.add_alarm_action(
            cw_actions.SnsAction(system_alerts_topic)
        )

        # Create alarm for processing success rate
        processing_success_alarm = cloudwatch.Alarm(
            self,
            "ProcessingSuccessAlarm",
            metric=processing_success_metric,
            threshold=90,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=3,
            alarm_description="Overall processing success rate is below 90%",
            alarm_name="MultiAccountAnomalyDetection-LowSuccessRate"
        )

        processing_success_alarm.add_alarm_action(
            cw_actions.SnsAction(system_alerts_topic)
        )

        # Create system health monitor Lambda function
        system_health_monitor_function = _lambda.Function(
            self,
            "SystemHealthMonitorFunction",
            description="Monitor system health and publish custom metrics",
            code=_lambda.Code.from_asset(
                path.join(LAMBDA_DIR, "SystemHealthMonitor")
            ),
            handler="main.handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            timeout=Duration.seconds(300),
            memory_size=256,
            environment={
                "OPENSEARCH_ENDPOINT": opensearch_domain.domain_endpoint if opensearch_domain else "",
                "LOGS_FUNCTION_NAME": multi_account_logs_function.function_name,
                "Q_CONNECTOR_FUNCTION_NAME": q_connector_function.function_name,
                "SNS_TOPIC_ARN": system_alerts_topic.topic_arn,
            },
        )

        # Grant permissions to system health monitor
        system_health_monitor_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "cloudwatch:PutMetricData",
                    "lambda:GetFunction",
                    "lambda:ListTags",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                    "logs:GetLogEvents",
                    "sns:Publish"
                ],
                resources=["*"]
            )
        )

        if opensearch_domain:
            system_health_monitor_function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=[
                        "es:ESHttpGet",
                        "es:ESHttpHead"
                    ],
                    resources=[f"{opensearch_domain.domain_arn}/*"]
                )
            )

        # Schedule system health monitoring every 5 minutes
        events.Rule(
            self,
            "SystemHealthMonitorRule",
            description="Trigger system health monitoring every 5 minutes",
            schedule=events.Schedule.rate(Duration.minutes(5)),
            targets=[targets.LambdaFunction(system_health_monitor_function)]
        )

        # Create dead letter queues for failed processing
        multi_account_logs_dlq = _lambda.Function(
            self,
            "MultiAccountLogsDLQHandler",
            description="Handle failed multi-account log processing events",
            code=_lambda.Code.from_asset(
                path.join(LAMBDA_DIR, "DeadLetterQueue")
            ),
            handler="dlq_handler.handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            timeout=Duration.seconds(60),
            memory_size=128,
            environment={
                "SNS_TOPIC_ARN": system_alerts_topic.topic_arn,
                "SOURCE_FUNCTION": "MultiAccountLogsFunction"
            }
        )

        # Grant SNS publish permissions to DLQ handler
        system_alerts_topic.grant_publish(multi_account_logs_dlq)
        
        # Outputs
        CfnOutput(
            self,
            "MultiAccountLogsFunctionArn",
            value=multi_account_logs_function.function_arn,
            description="ARN of multi-account logs processing function",
        )

        CfnOutput(
            self,
            "QBusinessConnectorFunctionArn",
            value=q_connector_function.function_arn,
            description="ARN of Q Business connector function",
        )

        CfnOutput(
            self,
            "QBusinessStatus",
            value="Enabled - Natural language insights active",
            description="Q Business integration status",
        )

        CfnOutput(
            self,
            "SystemAlertsTopicArn",
            value=system_alerts_topic.topic_arn,
            description="ARN of SNS topic for system alerts",
        )

        CfnOutput(
            self,
            "MonitoringDashboardName",
            value=dashboard.dashboard_name,
            description="Name of CloudWatch dashboard for system monitoring",
        )

        CfnOutput(
            self,
            "SystemHealthMonitorFunctionArn",
            value=system_health_monitor_function.function_arn,
            description="ARN of system health monitoring function",
        )

        # Store references
        self.logs_function = multi_account_logs_function
        self.q_connector_function = q_connector_function
        self.nl_insights_function = nl_insights_function
        self.system_alerts_topic = system_alerts_topic
        self.dashboard = dashboard
        self.system_health_monitor_function = system_health_monitor_function
