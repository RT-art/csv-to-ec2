import boto3
import csv
import os
import urllib.parse

s3 = boto3.client('s3')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    """
    S3へのCSVファイルアップロードをトリガーに実行されるメイン関数。
    CSVファイルの内容に基づき、EC2インスタンスを作成します。
    作成されるすべてのインスタンスには、SSM（Systems Manager）が有効化されます。
    """
    # イベント情報からバケット名とファイル名（キー）を取得
    bucket = event['Records'][0]['s3']['bucket']['name']
    # URLエンコードされたキーをデコード
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    print(f"処理開始: s3://{bucket}/{key}")

    try:
        # 環境変数から必須設定を取得
        target_subnet_id = os.environ['TARGET_SUBNET_ID']
        ssm_instance_profile_arn = os.environ['SSM_INSTANCE_PROFILE_ARN']
    except KeyError as e:
        print(f"致命的なエラー: 環境変数 {e} が設定されていません。")
        raise

    try:
        # S3からCSVファイルを取得して読み込む
        response = s3.get_object(Bucket=bucket, Key=key)
        # splitlines()で各行をリストに
        lines = response['Body'].read().decode('utf-8').splitlines()
        reader = csv.DictReader(lines)

        for row in reader:
            try:
                ami_id = row.get('ami_id')
                instance_type = row.get('instance_type')

                # 必須項目がなければスキップ
                if not all([ami_id, instance_type]):
                    print(f"必須項目（ami_id, instance_type）が不足しているため、この行をスキップします: {row}")
                    continue
                
                print(f"EC2インスタンスを作成中... AMI: {ami_id}, タイプ: {instance_type}")

                # EC2インスタンス作成APIのパラメータを設定
                run_instances_params = {
                    'ImageId': ami_id,
                    'InstanceType': instance_type,
                    'SubnetId': target_subnet_id,
                    'MinCount': 1,
                    'MaxCount': 1,
                    # SSMを有効にするためのIAMインスタンスプロファイルを常にアタッチ
                    'IamInstanceProfile': {
                        'Arn': ssm_instance_profile_arn
                    },
                    'TagSpecifications': [{
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': f'auto-created-from-{os.path.basename(key)}'},
                            {'Key': 'SourceFile', 'Value': f's3://{bucket}/{key}'}
                        ]
                    }]
                }
                
                instance_response = ec2.run_instances(**run_instances_params)
                
                instance_id = instance_response['Instances'][0]['InstanceId']
                print(f"インスタンス作成成功: {instance_id}")

            except Exception as e:
                # 行単位のエラーはログに出力して処理を続行
                print(f"行の処理中にエラーが発生したためスキップします: {row}, エラー: {e}")

    except Exception as e:
        print(f"致命的なエラーが発生しました: {e}")
        # 致命的なエラーの場合はLambdaの実行を失敗させる
        raise

    print(f"処理完了: s3://{bucket}/{key}")
    return {'status': 'success'}
