from os import path
from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_opensearchservice as opensearch,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_logs_destinations as destinations,
    CustomResource,
)
from constructs import Construct

PWD = path.dirname(path.realpath(__file__))
LAMBDA_DIR = path.join(PWD, "..", "..", "lambdas")
SHARED_DIR = path.join(PWD, "..", "..", "shared")


class EnhancedAnomalyDetectorStack(Stack):
    """
    Enhanced anomaly detector stack with multi-account support and
    Amazon Q for Business integration for natural language insights.
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

        # Add OpenSearch permissions
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
                "OPENSEARCH_DOMAIN_ENDPOINT": opensearch_domain.domain_endpoint,
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
                "OPENSEARCH_HOST": opensearch_domain.domain_endpoint,
                "ENABLE_MULTI_ACCOUNT": "true",
            },
        )

        # Add OpenSearch admin permissions
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
        # Note: Using a simplified approach since Provider construct may not be available
        CustomResource(
            self,
            "CrossAccountAnomalyConfig",
            service_token=cross_account_config_function.function_arn,
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

        # Amazon Q for Business connector Lambda
        q_connector_role = iam.Role(
            self,
            "QBusinessConnectorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Amazon Q Business connector",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Add permissions for Q Business
        q_connector_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "qbusiness:PutDocument",
                    "qbusiness:DeleteDocument",
                    "qbusiness:BatchPutDocument",
                    "qbusiness:BatchDeleteDocument",
                ],
                resources=["*"],  # Will be restricted to specific Q app later
            )
        )

        # Add OpenSearch read permissions
        q_connector_role.add_to_policy(
            iam.PolicyStatement(
                actions=["es:ESHttpGet", "es:ESHttpPost"],
                resources=[f"{opensearch_domain.domain_arn}/*"],
            )
        )

        # Q Business connector function
        q_connector_function = _lambda.Function(
            self,
            "QBusinessConnectorFunction",
            description="Sync anomaly data to Amazon Q for Business",
            code=_lambda.Code.from_asset(path.join(LAMBDA_DIR, "QBusinessConnector")),
            handler="main.handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            timeout=Duration.seconds(900),
            memory_size=1024,
            role=q_connector_role,
            environment={
                "OPENSEARCH_HOST": opensearch_domain.domain_endpoint,
                "Q_APPLICATION_ID": "",  # To be filled by Q Business stack
                "Q_INDEX_ID": "",  # To be filled by Q Business stack
            },
        )

        # Natural Language Insights Lambda
        nl_insights_role = iam.Role(
            self,
            "NLInsightsRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Natural Language Insights processing",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        # Add Q Business chat permissions
        nl_insights_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "qbusiness:Chat",
                    "qbusiness:ChatSync",
                    "qbusiness:GetChatHistory",
                ],
                resources=["*"],
            )
        )

        # Add CloudWatch and Cost Explorer permissions for enrichment
        nl_insights_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ce:GetCostAndUsage",
                    "ce:GetCostForecast",
                    "cloudwatch:GetMetricStatistics",
                    "cloudwatch:ListMetrics",
                ],
                resources=["*"],
            )
        )

        nl_insights_function = _lambda.Function(
            self,
            "NLInsightsFunction",
            description="Generate natural language insights using Amazon Q",
            code=_lambda.Code.from_asset(path.join(LAMBDA_DIR, "QBusinessConnector")),
            handler="insights.handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            timeout=Duration.seconds(300),
            memory_size=512,
            role=nl_insights_role,
            environment={
                "Q_APPLICATION_ID": "",  # To be filled after Q app creation
                "ENABLE_COST_ANALYSIS": "true",
                "ENABLE_ROOT_CAUSE_ANALYSIS": "true",
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
            "QConnectorFunctionArn",
            value=q_connector_function.function_arn,
            description="ARN of Q Business connector function",
        )

        CfnOutput(
            self,
            "NLInsightsFunctionArn",
            value=nl_insights_function.function_arn,
            description="ARN of Natural Language Insights function",
        )

        # Store references
        self.logs_function = multi_account_logs_function
        self.q_connector_function = q_connector_function
        self.nl_insights_function = nl_insights_function
