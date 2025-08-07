import boto3
import csv
import os
import urllib.parse

s3 = boto3.client('s3')
ec2 = boto3.client('ec2')

SSM_INSTANCE_PROFILE_ARN = os.environ.get('SSM_INSTANCE_PROFILE_ARN')

def lambda_handler(event, context):
    """
    S3へのCSVファイルアップロードをトリガーに実行されるメイン関数。
    """
    # イベント情報からバケット名とファイル名（キー）を取得
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    print(f"処理開始: s3://{bucket}/{key}")

    try:
        subnet_id = os.environ['TARGET_SUBNET_ID']
    except KeyError:
        print("Fatal error: TARGET_SUBNET_ID environment variable is not set.")
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
                    print(f"Skipping row due to missing required fields: {row}")
                    continue

                run_instances_params = {
                    'ImageId': ami_id,
                    'InstanceType': instance_type,
                    'SubnetId': subnet_id,
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

                enable_ssm = row.get('enable_ssm', 'OFF').upper() == 'ON'
                
                if enable_ssm and SSM_INSTANCE_PROFILE_ARN:
                    run_instances_params['IamInstanceProfile'] = {
                        'Arn': SSM_INSTANCE_PROFILE_ARN
                    }
                    print(f"Creating EC2 instance with SSM enabled: AMI={ami_id}, Type={instance_type}")
                else:
                    print(f"Creating EC2 instance: AMI={ami_id}, Type={instance_type}")
                
                instance_response = ec2.run_instances(**run_instances_params)
                
                instance_id = instance_response['Instances'][0]['InstanceId']
                print(f"Instance creation successful: {instance_id}")

            except Exception as e:
                print(f"Error processing row, skipping: {row}, Error: {e}")

    except Exception as e:
        print(f"Fatal error occurred: {e}")
        raise e

    print(f"処理完了: s3://{bucket}/{key}")
    return {'status': 'success'}
