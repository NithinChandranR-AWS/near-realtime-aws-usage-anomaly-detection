#!/usr/bin/env python3
import boto3
import json

# Initialize CloudFormation client
cf = boto3.client('cloudformation')

# List of stack names to check
stack_names = [
    'OrganizationTrailStack',
    'EnhancedUsageAnomalyDetectorStack',
    'MultiAccountAnomalyStack'
]

print("Checking CloudFormation stack status...\n")

for stack_name in stack_names:
    try:
        response = cf.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        print(f"Stack: {stack_name}")
        print(f"  Status: {stack['StackStatus']}")
        
        # Check for any errors
        if 'StackStatusReason' in stack:
            print(f"  Reason: {stack['StackStatusReason']}")
            
        # Check outputs
        if 'Outputs' in stack:
            print("  Outputs:")
            for output in stack['Outputs']:
                print(f"    {output['OutputKey']}: {output['OutputValue']}")
        print()
        
    except cf.exceptions.ClientError as e:
        if 'does not exist' in str(e):
            print(f"Stack: {stack_name} - Does not exist")
        else:
            print(f"Stack: {stack_name} - Error: {str(e)}")
        print()

print("\nChecking CloudTrail configuration...")
try:
    ct = boto3.client('cloudtrail')
    trails = ct.describe_trails()
    
    for trail in trails['trailList']:
        if 'org-trail' in trail['Name']:
            print(f"\nTrail: {trail['Name']}")
            print(f"  S3 Bucket: {trail['S3BucketName']}")
            print(f"  Is Organization Trail: {trail.get('IsOrganizationTrail', False)}")
            print(f"  Is Multi-Region: {trail.get('IsMultiRegionTrail', False)}")
            
            # Get trail status
            status = ct.get_trail_status(Name=trail['TrailARN'])
            print(f"  Is Logging: {status.get('IsLogging', False)}")
            
            # Get event selectors
            selectors = ct.get_event_selectors(TrailName=trail['TrailARN'])
            print(f"  Event Selectors:")
            for selector in selectors['EventSelectors']:
                print(f"    - Management Events: {selector.get('IncludeManagementEvents', False)}")
                print(f"    - Read/Write: {selector.get('ReadWriteType', 'None')}")
                if 'DataResources' in selector:
                    print(f"    - Data Resources:")
                    for resource in selector['DataResources']:
                        print(f"      - Type: {resource['Type']}")
                        print(f"      - Values: {resource['Values']}")
                        
except Exception as e:
    print(f"Error checking CloudTrail: {str(e)}")
