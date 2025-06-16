from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_iam as iam,
    aws_s3 as s3,
    aws_kms as kms,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as _lambda,
    CfnResource,
)
from constructs import Construct
from typing import List


class QBusinessStack(Stack):
    """
    Stack for Amazon Q for Business application to provide natural language
    insights for AWS usage anomalies.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        q_connector_function: _lambda.Function = None,
        opensearch_domain = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create KMS key for Q Business encryption
        q_kms_key = kms.Key(
            self,
            "QBusinessKey",
            description="KMS key for Amazon Q for Business encryption",
            enable_key_rotation=True,
        )

        # Create S3 bucket for Q Business data
        q_data_bucket = s3.Bucket(
            self,
            "QBusinessDataBucket",
            bucket_name=f"q-business-anomaly-data-{self.account}-{self.region}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=q_kms_key,
            enforce_ssl=True,
            versioned=True,
        )

        # Create IAM role for Q Business
        q_service_role = iam.Role(
            self,
            "QBusinessServiceRole",
            assumed_by=iam.ServicePrincipal("qbusiness.amazonaws.com"),
            description="Service role for Amazon Q for Business",
        )

        # Add permissions for Q Business
        q_service_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=[
                    q_data_bucket.bucket_arn,
                    f"{q_data_bucket.bucket_arn}/*",
                ],
            )
        )

        q_service_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:CreateGrant",
                ],
                resources=[q_kms_key.key_arn],
            )
        )

        # Create Q Business application using CloudFormation
        q_application = CfnResource(
            self,
            "AnomalyInsightsQApp",
            type="AWS::QBusiness::Application",
            properties={
                "DisplayName": "AWS Usage Anomaly Insights",
                "Description": "Natural language insights for AWS usage anomalies using Amazon Q",
                "RoleArn": q_service_role.role_arn,
                "EncryptionConfiguration": {
                    "KmsKeyId": q_kms_key.key_id
                },
                "AttachmentsConfiguration": {
                    "AttachmentsControlMode": "ENABLED"
                }
            }
        )

        # Create Q Business index using CloudFormation
        q_index = CfnResource(
            self,
            "AnomalyInsightsIndex",
            type="AWS::QBusiness::Index",
            properties={
                "ApplicationId": q_application.ref,
                "DisplayName": "Anomaly Insights Index",
                "Description": "Index for AWS usage anomaly data and insights",
                "Type": "ENTERPRISE",
                "CapacityConfiguration": {
                    "Units": 1
                },
                "DocumentAttributeConfigurations": [
                    {
                        "Name": "account_id",
                        "Type": "STRING",
                        "Search": {
                            "Displayable": True,
                            "Facetable": True,
                            "Searchable": True,
                            "Sortable": True
                        }
                    },
                    {
                        "Name": "account_alias", 
                        "Type": "STRING",
                        "Search": {
                            "Displayable": True,
                            "Facetable": True,
                            "Searchable": True,
                            "Sortable": True
                        }
                    },
                    {
                        "Name": "event_name",
                        "Type": "STRING", 
                        "Search": {
                            "Displayable": True,
                            "Facetable": True,
                            "Searchable": True,
                            "Sortable": True
                        }
                    },
                    {
                        "Name": "severity",
                        "Type": "STRING",
                        "Search": {
                            "Displayable": True,
                            "Facetable": True,
                            "Searchable": True,
                            "Sortable": True
                        }
                    },
                    {
                        "Name": "anomaly_date",
                        "Type": "DATE",
                        "Search": {
                            "Displayable": True,
                            "Facetable": True,
                            "Searchable": True,
                            "Sortable": True
                        }
                    },
                    {
                        "Name": "event_count",
                        "Type": "LONG",
                        "Search": {
                            "Displayable": True,
                            "Facetable": True,
                            "Searchable": True,
                            "Sortable": True
                        }
                    }
                ]
            }
        )

        # Create Q Business connector Lambda function if not provided
        if q_connector_function is None:
            # Create IAM role for Q connector function
            q_connector_role = iam.Role(
                self,
                "QConnectorRole",
                assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                description="IAM role for Q Business connector Lambda function",
                managed_policies=[
                    iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
                ]
            )
            
            # Add permissions for OpenSearch and Q Business
            q_connector_role.add_to_policy(
                iam.PolicyStatement(
                    actions=[
                        "es:ESHttpGet",
                        "es:ESHttpPost",
                        "es:ESHttpPut",
                        "qbusiness:*",
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:ListBucket"
                    ],
                    resources=["*"]  # Will be refined in production
                )
            )
            
            # Create the Q connector Lambda function
            q_connector_function = _lambda.Function(
                self,
                "QConnectorFunction",
                description="Lambda function to sync OpenSearch data with Q Business",
                code=_lambda.Code.from_asset("lambdas/QBusinessConnector"),
                handler="main.handler",
                runtime=_lambda.Runtime.PYTHON_3_9,
                timeout=Duration.minutes(5),
                role=q_connector_role,
                environment={
                    "Q_APPLICATION_ID": q_application.ref,
                    "Q_INDEX_ID": q_index.ref,
                    "OPENSEARCH_ENDPOINT": opensearch_domain.domain_endpoint if opensearch_domain else "",
                    "S3_BUCKET": q_data_bucket.bucket_name
                }
            )
        
        # Create EventBridge rule to trigger Q connector
        sync_rule = events.Rule(
            self,
            "QSyncRule",
            description="Trigger Q Business sync every 15 minutes",
            schedule=events.Schedule.rate(Duration.minutes(15)),
        )

        sync_rule.add_target(targets.LambdaFunction(q_connector_function))

        # Outputs
        CfnOutput(
            self,
            "QApplicationId",
            value=q_application.ref,
            description="Amazon Q for Business Application ID",
        )

        CfnOutput(
            self,
            "QIndexId", 
            value=q_index.ref,
            description="Amazon Q for Business Index ID",
        )

        CfnOutput(
            self,
            "QBusinessStatus",
            value="Q Business resources created - manual configuration required",
            description="Q Business setup status",
        )

        # Store references
        self.q_application = q_application
        self.q_index = q_index
