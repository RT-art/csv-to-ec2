import boto3
import csv
import os
import urllib.parse

s3 = boto3.client('s3')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    """
    This function is triggered by a CSV file upload to S3. It reads the CSV
    and creates EC2 instances based on its content.
    """
    # Get bucket and key from the S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    print(f"Processing started for: s3://{bucket}/{key}")

    try:
        # These environment variables are critical, fail fast if they are not set.
        subnet_id = os.environ['TARGET_SUBNET_ID']
        ssm_profile_arn = os.environ['SSM_INSTANCE_PROFILE_ARN']
    except KeyError as e:
        print(f"Fatal error: Environment variable {e} is not set.")
        raise

    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        lines = response['Body'].read().decode('utf-8').splitlines()
        reader = csv.DictReader(lines)

        for row in reader:
            try:
                ami_id = row.get('ami_id')
                instance_type = row.get('instance_type')

                if not all([ami_id, instance_type]):
                    print(f"Skipping row due to missing required fields (ami_id, instance_type): {row}")
                    continue
                
                print(f"Creating EC2 instance with SSM: AMI={ami_id}, Type={instance_type}")
                
                instance_response = ec2.run_instances(
                    ImageId=ami_id,
                    InstanceType=instance_type,
                    SubnetId=subnet_id,
                    MinCount=1,
                    MaxCount=1,
                    IamInstanceProfile={
                        'Arn': ssm_profile_arn
                    },
                    TagSpecifications=[{
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': f'auto-created-from-{os.path.basename(key)}'},
                            {'Key': 'SourceFile', 'Value': f's3://{bucket}/{key}'}
                        ]
                    }]
                )
                
                instance_id = instance_response['Instances'][0]['InstanceId']
                print(f"Instance creation successful: {instance_id}")

            except Exception as e:
                print(f"Error processing row, skipping: {row}. Error: {e}")

    except Exception as e:
        print(f"A fatal error occurred while processing the file: {e}")
        raise e

    print(f"Processing complete for: s3://{bucket}/{key}")
    return {'status': 'success'}
