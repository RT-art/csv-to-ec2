# src/app.py
import boto3
import csv
import os
import urllib.parse

s3 = boto3.client('s3')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    # イベントソースからバケット名とファイルキーを取得
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    print(f"Processing file: s3://{bucket}/{key}")

    try:
        # S3からCSVファイルを取得
        response = s3.get_object(Bucket=bucket, Key=key)
        lines = response['Body'].read().decode('utf-8').splitlines()
        reader = csv.DictReader(lines)

        for row in reader:
            try:
                # CSVから必須パラメータを安全に読み取る
                subnet_id = row.get('subnet_id')
                ami_id = row.get('ami_id')
                instance_type = row.get('instance_type')

                # 必須項目が揃っているかチェック
                if not all([subnet_id, ami_id, instance_type]):
                    print(f"Skipping row due to missing required fields: {row}")
                    continue
                
                print(f"Creating EC2 instance with AMI: {ami_id}, Type: {instance_type} in Subnet: {subnet_id}")

                # EC2インスタンスを作成
                instance_response = ec2.run_instances(
                    ImageId=ami_id,
                    InstanceType=instance_type,
                    SubnetId=subnet_id,
                    MinCount=1,
                    MaxCount=1,
                    TagSpecifications=[{
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': f'Created from {os.path.basename(key)}'},
                            {'Key': 'SourceFile', 'Value': f's3://{bucket}/{key}'}
                        ]
                    }]
                )
                
                instance_id = instance_response['Instances'][0]['InstanceId']
                print(f"Successfully created instance: {instance_id}")

            except Exception as e:
                print(f"Error processing row: {row}. Error: {str(e)}")

    except Exception as e:
        print(f"Error getting file from S3. Error: {str(e)}")
        raise e