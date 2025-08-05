#!/usr/bin/env python3
"""
DynamoDB table definition for account metadata cache
"""

from aws_cdk import (
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    Duration
)
from constructs import Construct

def create_account_cache_table(scope: Construct, construct_id: str) -> dynamodb.Table:
    """
    Create DynamoDB table for caching account metadata
    """
    table = dynamodb.Table(
        scope,
        construct_id,
        table_name="account-metadata-cache",
        partition_key=dynamodb.Attribute(
            name="accountId",
            type=dynamodb.AttributeType.STRING
        ),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        removal_policy=RemovalPolicy.DESTROY,
        time_to_live_attribute="ttl",
        point_in_time_recovery=True,
        encryption=dynamodb.TableEncryption.AWS_MANAGED,
        stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES
    )
    
    # Add GSI for querying by account type
    table.add_global_secondary_index(
        index_name="AccountTypeIndex",
        partition_key=dynamodb.Attribute(
            name="accountType",
            type=dynamodb.AttributeType.STRING
        ),
        sort_key=dynamodb.Attribute(
            name="lastUpdated",
            type=dynamodb.AttributeType.STRING
        )
    )
    
    # Add GSI for querying by organizational unit
    table.add_global_secondary_index(
        index_name="OrganizationalUnitIndex",
        partition_key=dynamodb.Attribute(
            name="organizationalUnit",
            type=dynamodb.AttributeType.STRING
        ),
        sort_key=dynamodb.Attribute(
            name="lastUpdated",
            type=dynamodb.AttributeType.STRING
        )
    )
    
    return table