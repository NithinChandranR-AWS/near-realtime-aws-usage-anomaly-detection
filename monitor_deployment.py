#!/usr/bin/env python3
import boto3
import time
import sys

# Initialize CloudFormation client
cf = boto3.client('cloudformation')

# Stack names to monitor
stack_names = [
    'OrganizationTrailStack',
    'EnhancedUsageAnomalyDetectorStack',
    'MultiAccountAnomalyStack'
]

print("Monitoring CloudFormation deployment progress...\n")

# Keep track of completed stacks
completed_stacks = set()

while len(completed_stacks) < len(stack_names):
    for stack_name in stack_names:
        if stack_name in completed_stacks:
            continue
            
        try:
            response = cf.describe_stacks(StackName=stack_name)
            stack = response['Stacks'][0]
            status = stack['StackStatus']
            
            # Print status update
            print(f"[{time.strftime('%H:%M:%S')}] {stack_name}: {status}")
            
            # Check if stack is in a terminal state
            if status in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
                print(f"  ✅ {stack_name} deployed successfully!")
                completed_stacks.add(stack_name)
            elif 'FAILED' in status or 'ROLLBACK' in status:
                print(f"  ❌ {stack_name} failed!")
                if 'StackStatusReason' in stack:
                    print(f"  Reason: {stack['StackStatusReason']}")
                completed_stacks.add(stack_name)
                
        except cf.exceptions.ClientError as e:
            if 'does not exist' in str(e):
                print(f"[{time.strftime('%H:%M:%S')}] {stack_name}: Waiting to be created...")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] {stack_name}: Error - {str(e)}")
    
    # Wait before checking again
    if len(completed_stacks) < len(stack_names):
        time.sleep(10)
    print()

print("\nDeployment monitoring complete!")

# Final summary
print("\nFinal Stack Status:")
for stack_name in stack_names:
    try:
        response = cf.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        print(f"  {stack_name}: {stack['StackStatus']}")
        
        # Print outputs if available
        if 'Outputs' in stack and stack['StackStatus'] in ['CREATE_COMPLETE', 'UPDATE_COMPLETE']:
            print(f"  Outputs:")
            for output in stack['Outputs'][:3]:  # Show first 3 outputs
                print(f"    - {output['OutputKey']}: {output['OutputValue']}")
                
    except Exception as e:
        print(f"  {stack_name}: Not found or error")
