from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    aws_s3 as s3,
    aws_cloudtrail as cloudtrail,
    aws_organizations as organizations,
    aws_iam as iam,
    aws_kms as kms,
    aws_logs as logs,
)
from constructs import Construct


class OrganizationTrailStack(Stack):
    """
    Stack for creating an organization-wide CloudTrail that aggregates
    events from all member accounts for centralized anomaly detection.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create KMS key for trail encryption
        trail_key = kms.Key(
            self,
            "OrganizationTrailKey",
            description="KMS key for organization-wide CloudTrail encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Add key policy for CloudTrail service
        trail_key.add_to_resource_policy(
            iam.PolicyStatement(
                sid="Enable CloudTrail to encrypt logs",
                actions=["kms:GenerateDataKey*", "kms:DescribeKey"],
                resources=["*"],
                principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com")],
                conditions={
                    "StringLike": {
                        "kms:EncryptionContext:aws:cloudtrail:arn": f"arn:aws:cloudtrail:*:{self.account}:trail/*"
                    }
                },
            )
        )

        # Create centralized S3 bucket for organization trail
        org_trail_bucket = s3.Bucket(
            self,
            "OrganizationTrailBucket",
            bucket_name=f"org-trail-{self.account}-{self.region}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=trail_key,
            enforce_ssl=True,
            versioned=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="DeleteOldLogs",
                    enabled=True,
                    expiration=Duration.days(90),
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30),
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(60),
                        ),
                    ],
                )
            ],
        )

        # Add bucket policy for organization trail
        org_trail_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AWSCloudTrailAclCheck",
                actions=["s3:GetBucketAcl"],
                resources=[org_trail_bucket.bucket_arn],
                principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com")],
            )
        )

        org_trail_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AWSCloudTrailWrite",
                actions=["s3:PutObject"],
                resources=[f"{org_trail_bucket.bucket_arn}/*"],
                principals=[iam.ServicePrincipal("cloudtrail.amazonaws.com")],
                conditions={
                    "StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}
                },
            )
        )

        # Create CloudWatch log group for organization trail
        org_log_group = logs.LogGroup(
            self,
            "OrganizationTrailLogGroup",
            log_group_name=f"/aws/cloudtrail/organization/{self.stack_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create organization trail
        org_trail = cloudtrail.CfnTrail(
            self,
            "OrganizationTrail",
            trail_name=f"org-trail-{self.stack_name}",
            s3_bucket_name=org_trail_bucket.bucket_name,
            is_organization_trail=True,
            is_multi_region_trail=True,
            include_global_service_events=True,
            enable_log_file_validation=True,
            is_logging=True,
            event_selectors=[
                cloudtrail.CfnTrail.EventSelectorProperty(
                    read_write_type="All",
                    include_management_events=True,
                    data_resources=[
                        cloudtrail.CfnTrail.DataResourceProperty(
                            type="AWS::EC2::Instance", values=["arn:aws:ec2:*:*:instance/*"]
                        ),
                        cloudtrail.CfnTrail.DataResourceProperty(
                            type="AWS::Lambda::Function", values=["arn:aws:lambda:*:*:function/*"]
                        ),
                    ],
                )
            ],
            cloud_watch_logs_log_group_arn=org_log_group.log_group_arn,
            cloud_watch_logs_role_arn=self._create_cloudtrail_log_role().role_arn,
            kms_key_id=trail_key.key_id,
        )

        # Outputs
        CfnOutput(
            self,
            "OrganizationTrailBucketName",
            value=org_trail_bucket.bucket_name,
            description="S3 bucket containing organization-wide CloudTrail logs",
        )

        CfnOutput(
            self,
            "OrganizationTrailLogGroupName",
            value=org_log_group.log_group_name,
            description="CloudWatch log group for organization trail",
        )

        CfnOutput(
            self,
            "OrganizationTrailArn",
            value=f"arn:aws:cloudtrail:{self.region}:{self.account}:trail/{org_trail.trail_name}",
            description="ARN of the organization trail",
        )

        # Store references for cross-stack usage
        self.trail_bucket = org_trail_bucket
        self.log_group = org_log_group
        self.trail_key = trail_key

    def _create_cloudtrail_log_role(self) -> iam.Role:
        """Create IAM role for CloudTrail to write to CloudWatch Logs"""
        role = iam.Role(
            self,
            "CloudTrailLogRole",
            assumed_by=iam.ServicePrincipal("cloudtrail.amazonaws.com"),
            description="Role for CloudTrail to write to CloudWatch Logs",
        )

        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=["*"],
            )
        )

        return role
