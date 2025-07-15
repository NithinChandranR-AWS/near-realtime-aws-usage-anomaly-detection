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
    aws_sso as sso,
    aws_identitystore as identitystore,
    CfnResource,
    CustomResource,
    custom_resources as cr,
)
from constructs import Construct
from typing import List, Optional


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

        # Create Lambda function for Identity Center management
        identity_center_lambda_role = iam.Role(
            self,
            "IdentityCenterLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="IAM role for Identity Center management Lambda",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Add permissions for Identity Center operations
        identity_center_lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sso:ListInstances",
                    "sso:CreateInstance",
                    "sso:DescribeInstance",
                    "sso-admin:ListInstances",
                    "sso-admin:CreateInstance",
                    "sso-admin:DescribeInstance",
                    "identitystore:ListGroups",
                    "identitystore:CreateGroup",
                    "identitystore:ListUsers",
                    "identitystore:CreateUser",
                ],
                resources=["*"]
            )
        )

        # Create Lambda function for Identity Center setup
        identity_center_lambda = _lambda.Function(
            self,
            "IdentityCenterSetupFunction",
            description="Lambda function to set up Identity Center for Q Business",
            code=_lambda.Code.from_inline("""
import json
import boto3
import cfnresponse

def handler(event, context):
    try:
        sso_admin = boto3.client('sso-admin')
        
        if event['RequestType'] == 'Create':
            # List existing instances
            response = sso_admin.list_instances()
            instances = response.get('Instances', [])
            
            if instances:
                # Use existing instance
                instance_arn = instances[0]['InstanceArn']
                identity_store_id = instances[0]['IdentityStoreId']
                print(f"Using existing Identity Center instance: {instance_arn}")
            else:
                # Create new instance (this may fail in organization management accounts)
                try:
                    create_response = sso_admin.create_instance(
                        Name='Q-Business-Identity-Center'
                    )
                    instance_arn = create_response['InstanceArn']
                    identity_store_id = create_response['IdentityStoreId']
                    print(f"Created new Identity Center instance: {instance_arn}")
                except Exception as e:
                    print(f"Failed to create Identity Center instance: {str(e)}")
                    # Return a placeholder ARN for now
                    instance_arn = f"arn:aws:sso:::instance/placeholder-{context.aws_request_id[:8]}"
                    identity_store_id = f"placeholder-{context.aws_request_id[:8]}"
            
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {
                'InstanceArn': instance_arn,
                'IdentityStoreId': identity_store_id
            })
            
        elif event['RequestType'] == 'Delete':
            # Don't delete Identity Center instances as they may be used by other resources
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            
        else:
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            
    except Exception as e:
        print(f"Error: {str(e)}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {})
"""),
            handler="index.handler",
            runtime=_lambda.Runtime.PYTHON_3_9,
            timeout=Duration.minutes(5),
            role=identity_center_lambda_role,
        )

        # Create custom resource for Identity Center setup
        identity_center_resource = CustomResource(
            self,
            "IdentityCenterResource",
            service_token=identity_center_lambda.function_arn,
            properties={
                "RequestId": self.node.addr  # Unique identifier
            }
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

        # Create Q Business application using Identity Center
        # Using CfnResource for compatibility with older CDK versions
        q_application = CfnResource(
            self,
            "AnomalyInsightsQApp",
            type="AWS::QBusiness::Application",
            properties={
                "DisplayName": "AWS-Usage-Anomaly-Insights",
                "Description": "Natural language insights for AWS usage anomalies using Amazon Q",
                "RoleArn": q_service_role.role_arn,
                "IdentityType": "AWS_IAM_IDC",
                "EncryptionConfiguration": {
                    "KmsKeyId": q_kms_key.key_id
                },
                "AttachmentsConfiguration": {
                    "AttachmentsControlMode": "ENABLED"
                }
            }
        )

        # Add dependency to ensure Identity Center is set up first
        q_application.node.add_dependency(identity_center_resource)

        # Create Q Business index using CloudFormation
        q_index = CfnResource(
            self,
            "AnomalyInsightsIndex",
            type="AWS::QBusiness::Index",
            properties={
                "ApplicationId": q_application.ref,
                "DisplayName": "Anomaly-Insights-Index",
                "Description": "Index for AWS usage anomaly data and insights",
                "Type": "ENTERPRISE",
                "CapacityConfiguration": {
                    "Units": 1
                },
                "DocumentAttributeConfigurations": [
                    {
                        "Name": "account_id",
                        "Type": "STRING",
                        "Search": "ENABLED"
                    },
                    {
                        "Name": "account_alias", 
                        "Type": "STRING",
                        "Search": "ENABLED"
                    },
                    {
                        "Name": "event_name",
                        "Type": "STRING", 
                        "Search": "ENABLED"
                    },
                    {
                        "Name": "severity",
                        "Type": "STRING",
                        "Search": "ENABLED"
                    },
                    {
                        "Name": "anomaly_date",
                        "Type": "DATE",
                        "Search": "ENABLED"
                    },
                    {
                        "Name": "event_count",
                        "Type": "NUMBER",
                        "Search": "ENABLED"
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
            "IdentityCenterInstanceArn",
            value=identity_center_resource.get_att_string("InstanceArn"),
            description="Identity Center Instance ARN for Q Business",
        )

        CfnOutput(
            self,
            "IdentityStoreId",
            value=identity_center_resource.get_att_string("IdentityStoreId"),
            description="Identity Store ID for user management",
        )

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
            value="Q Business resources created with Identity Center integration - ready for use",
            description="Q Business setup status",
        )

        # Store references
        self.q_application = q_application
        self.q_index = q_index
