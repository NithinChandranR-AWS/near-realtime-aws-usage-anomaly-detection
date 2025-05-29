from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    aws_iam as iam,
    aws_qbusiness as qbusiness,
    aws_s3 as s3,
    aws_kms as kms,
    aws_events as events,
    aws_events_targets as targets,
    aws_lambda as _lambda,
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
        q_connector_function: _lambda.Function,
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

        # Create Q Business application
        q_application = qbusiness.CfnApplication(
            self,
            "AnomalyInsightsQApp",
            display_name="AWS Usage Anomaly Insights",
            description="Natural language insights for AWS usage anomalies using Amazon Q",
            role_arn=q_service_role.role_arn,
            encryption_configuration=qbusiness.CfnApplication.EncryptionConfigurationProperty(
                kms_key_id=q_kms_key.key_id
            ),
            attachments_configuration=qbusiness.CfnApplication.AttachmentsConfigurationProperty(
                attachments_control_mode="ENABLED"
            ),
        )

        # Create Q Business index
        q_index = qbusiness.CfnIndex(
            self,
            "AnomalyInsightsIndex",
            application_id=q_application.attr_application_id,
            display_name="Anomaly Insights Index",
            description="Index for AWS usage anomaly data and insights",
            type="ENTERPRISE",
            capacity_configuration=qbusiness.CfnIndex.IndexCapacityConfigurationProperty(
                units=1
            ),
            document_attribute_configurations=[
                qbusiness.CfnIndex.DocumentAttributeConfigurationProperty(
                    name="account_id",
                    type="STRING",
                    search=qbusiness.CfnIndex.DocumentAttributeSearchProperty(
                        displayable=True,
                        facetable=True,
                        searchable=True,
                        sortable=True,
                    ),
                ),
                qbusiness.CfnIndex.DocumentAttributeConfigurationProperty(
                    name="account_alias",
                    type="STRING",
                    search=qbusiness.CfnIndex.DocumentAttributeSearchProperty(
                        displayable=True,
                        facetable=True,
                        searchable=True,
                        sortable=True,
                    ),
                ),
                qbusiness.CfnIndex.DocumentAttributeConfigurationProperty(
                    name="event_name",
                    type="STRING",
                    search=qbusiness.CfnIndex.DocumentAttributeSearchProperty(
                        displayable=True,
                        facetable=True,
                        searchable=True,
                        sortable=True,
                    ),
                ),
                qbusiness.CfnIndex.DocumentAttributeConfigurationProperty(
                    name="severity",
                    type="STRING",
                    search=qbusiness.CfnIndex.DocumentAttributeSearchProperty(
                        displayable=True,
                        facetable=True,
                        searchable=True,
                        sortable=True,
                    ),
                ),
                qbusiness.CfnIndex.DocumentAttributeConfigurationProperty(
                    name="anomaly_date",
                    type="DATE",
                    search=qbusiness.CfnIndex.DocumentAttributeSearchProperty(
                        displayable=True,
                        facetable=True,
                        searchable=True,
                        sortable=True,
                    ),
                ),
                qbusiness.CfnIndex.DocumentAttributeConfigurationProperty(
                    name="event_count",
                    type="LONG",
                    search=qbusiness.CfnIndex.DocumentAttributeSearchProperty(
                        displayable=True,
                        facetable=True,
                        searchable=True,
                        sortable=True,
                    ),
                ),
            ],
        )

        # Create Q Business data source (custom connector)
        q_data_source = qbusiness.CfnDataSource(
            self,
            "AnomalyDataSource",
            application_id=q_application.attr_application_id,
            index_id=q_index.attr_index_id,
            display_name="OpenSearch Anomaly Data",
            description="Data source for OpenSearch anomaly detection results",
            type="CUSTOM",
            configuration={
                "type": "CUSTOM",
                "customDataSourceConfiguration": {
                    "roleArn": q_connector_function.role.role_arn,
                    "apiSchemaType": "OPEN_API_V3",
                }
            },
            role_arn=q_service_role.role_arn,
            sync_schedule="cron(0/15 * * * ? *)",  # Every 15 minutes
        )

        # Update Lambda environment variables
        q_connector_function.add_environment(
            "Q_APPLICATION_ID", q_application.attr_application_id
        )
        q_connector_function.add_environment("Q_INDEX_ID", q_index.attr_index_id)

        # Create EventBridge rule to trigger Q connector
        sync_rule = events.Rule(
            self,
            "QSyncRule",
            description="Trigger Q Business sync every 15 minutes",
            schedule=events.Schedule.rate(Duration.minutes(15)),
        )

        sync_rule.add_target(targets.LambdaFunction(q_connector_function))

        # Create retriever for Q Business
        q_retriever = qbusiness.CfnRetriever(
            self,
            "AnomalyRetriever",
            application_id=q_application.attr_application_id,
            type="NATIVE_INDEX",
            display_name="Anomaly Insights Retriever",
            configuration={
                "nativeIndexConfiguration": {
                    "indexId": q_index.attr_index_id,
                    "boostingOverride": {
                        "dateOrTimestampBoostingConfigurations": [
                            {
                                "fieldName": "anomaly_date",
                                "boostingLevel": "HIGH",
                                "boostingDurationInMinutes": 1440,  # 24 hours
                            }
                        ],
                        "stringAttributeBoostingConfigurations": [
                            {
                                "fieldName": "severity",
                                "boostingLevel": "HIGH",
                                "attributeValueBoosting": {
                                    "HIGH": "HIGH",
                                    "MEDIUM": "MEDIUM",
                                    "LOW": "LOW",
                                },
                            }
                        ],
                    },
                }
            },
        )

        # Create web experience for Q Business (optional)
        q_web_experience = qbusiness.CfnWebExperience(
            self,
            "AnomalyInsightsWebExperience",
            application_id=q_application.attr_application_id,
            title="AWS Usage Anomaly Insights",
            subtitle="Natural language insights for your AWS usage patterns",
            welcome_message="Welcome! Ask me about AWS usage anomalies, cost impacts, and recommendations.",
            sample_prompts_control_mode="ENABLED",
        )

        # Outputs
        CfnOutput(
            self,
            "QApplicationId",
            value=q_application.attr_application_id,
            description="Amazon Q for Business Application ID",
        )

        CfnOutput(
            self,
            "QIndexId",
            value=q_index.attr_index_id,
            description="Amazon Q for Business Index ID",
        )

        CfnOutput(
            self,
            "QWebExperienceUrl",
            value=q_web_experience.attr_default_endpoint,
            description="Amazon Q for Business Web Experience URL",
        )

        # Store references
        self.q_application = q_application
        self.q_index = q_index
        self.q_web_experience = q_web_experience
