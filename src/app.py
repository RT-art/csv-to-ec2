import boto3
import csv
import os
import urllib.parse

s3 = boto3.client('s3')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    print(f"処理開始: s3://{bucket}/{key}")

    try:
        target_subnet_id = os.environ['TARGET_SUBNET_ID']
        ssm_instance_profile_arn = os.environ['SSM_INSTANCE_PROFILE_ARN']
        stack_name = os.environ.get('AWS_STACK_NAME', 'unknown-stack')
    except KeyError as e:
        print(f"エラー: 環境変数 {e} が設定されていません。")
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
                    print(f"必須項目（ami_id, instance_type）が不足しているため、この行をスキップします: {row}")
                    continue
                
                print(f"EC2インスタンスを作成中... AMI: {ami_id}, タイプ: {instance_type}")

                run_instances_params = {
                    'ImageId': ami_id,
                    'InstanceType': instance_type,
                    'SubnetId': target_subnet_id,
                    'MinCount': 1,
                    'MaxCount': 1,
                    'IamInstanceProfile': {
                        'Arn': ssm_instance_profile_arn
                    },
                    'TagSpecifications': [{
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': f'auto-created-from-{os.path.basename(key)}'},
                            {'Key': 'SourceFile', 'Value': f's3://{bucket}/{key}'},
                            {'Key': 'CreatedByStack', 'Value': stack_name}
                        ]
                    }]
                }
                
                instance_response = ec2.run_instances(**run_instances_params)
                
                instance_id = instance_response['Instances'][0]['InstanceId']
                print(f"インスタンス作成成功: {instance_id}")

            except Exception as e:
                print(f"行の処理中にエラーが発生したためスキップします: {row}, エラー: {e}")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        raise

    print(f"処理完了: s3://{bucket}/{key}")
    return {'status': 'success'}
