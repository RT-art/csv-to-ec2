import boto3
import json
import os
import urllib.parse

s3 = boto3.client('s3')
ec2 = boto3.client('ec2')

# The ARN for the IAM instance profile is passed as an environment variable
SSM_INSTANCE_PROFILE_ARN = os.environ.get('SSM_INSTANCE_PROFILE_ARN')

def lambda_handler(event, context):
    """
    Main function executed when a JSON file is uploaded to S3.
    """
    # Get bucket name and file name (key) from event information
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    print(f"Processing started: s3://{bucket}/{key}")

    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read().decode('utf-8')
        instances_to_create = json.loads(content)

        # Assume JSON content is a list
        if not isinstance(instances_to_create, list):
            print(f"Error: JSON file content is not a list. File: s3://{bucket}/{key}")
            return {'status': 'failed', 'reason': 'Invalid JSON format'}

        for item in instances_to_create:
            try:
                # subnet_id is now a required field in the JSON
                subnet_id = item.get('subnet_id')
                ami_id = item.get('ami_id')
                instance_type = item.get('instance_type')

                # Check for all required fields
                if not all([subnet_id, ami_id, instance_type]):
                    print(f"Skipping item due to missing required fields (subnet_id, ami_id, instance_type): {item}")
                    continue

                run_instances_params = {
                    'ImageId': ami_id,
                    'InstanceType': instance_type,
                    'SubnetId': subnet_id, # Use subnet_id from the JSON item
                    'MinCount': 1,
                    'MaxCount': 1,
                    'TagSpecifications': [{
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': f'auto-created-from-{os.path.basename(key)}'},
                            {'Key': 'SourceFile', 'Value': f's3://{bucket}/{key}'}
                        ]
                    }]
                }

                enable_ssm = str(item.get('enable_ssm', 'OFF')).upper() == 'ON'
                
                if enable_ssm and SSM_INSTANCE_PROFILE_ARN:
                    run_instances_params['IamInstanceProfile'] = {
                        'Arn': SSM_INSTANCE_PROFILE_ARN
                    }
                    print(f"Creating EC2 instance with SSM enabled: AMI={ami_id}, Type={instance_type}, Subnet={subnet_id}")
                else:
                    print(f"Creating EC2 instance: AMI={ami_id}, Type={instance_type}, Subnet={subnet_id}")
                
                instance_response = ec2.run_instances(**run_instances_params)
                
                instance_id = instance_response['Instances'][0]['InstanceId']
                print(f"Instance creation successful: {instance_id}")

            except Exception as e:
                print(f"Error processing item, skipping: {item}, Error: {e}")

    except json.JSONDecodeError as e:
        print(f"Fatal error: Failed to decode JSON from s3://{bucket}/{key}. Error: {e}")
        raise e
    except Exception as e:
        print(f"Fatal error occurred: {e}")
        raise e

    print(f"Processing complete: s3://{bucket}/{key}")
    return {'status': 'success'}
