import boto3
from botocore.exceptions import ClientError

cfn_client = boto3.client('cloudformation')

def lambda_handler(event, context):
    """
    指定されたCloudFormationスタックのOutputから 'InstanceId' を取得して返す。
    Step Functionsから呼び出されることを想定。
    """
    stack_name = event.get('StackName')
    if not stack_name:
        raise ValueError("Error: StackName not provided in the input event.")

    print(f"Fetching outputs for stack: {stack_name}")

    try:
        response = cfn_client.describe_stacks(StackName=stack_name)
        
        if not response.get('Stacks'):
            raise ValueError(f"Stack '{stack_name}' not found.")
            
        outputs = response['Stacks'][0].get('Outputs', [])
        
        instance_id = next((o['OutputValue'] for o in outputs if o['OutputKey'] == 'InstanceId'), None)

        if not instance_id:
            raise ValueError(f"Could not find 'InstanceId' in outputs for stack {stack_name}.")
            
        print(f"Found InstanceId: {instance_id}")
        return {'InstanceId': instance_id}

    except ClientError as e:
        print(f"AWS Client Error: {e}")
        raise e