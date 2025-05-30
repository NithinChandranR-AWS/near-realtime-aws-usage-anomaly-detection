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

        # Add permissions for Q Business connector
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

        # Store references
        self.logs_function = multi_account_logs_function
        self.q_connector_function = q_connector_function
        self.nl_insights_function = nl_insights_function
