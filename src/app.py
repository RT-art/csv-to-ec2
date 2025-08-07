import boto3
import csv
import os
import urllib.parse

# boto3クライアントを初期化
s3 = boto3.client('s3')
ec2 = boto3.client('ec2')

def lambda_handler(event, context):
    """
    S3へのCSVファイルアップロードをトリガーに実行されるメイン関数。
    """
    # イベント情報からバケット名とファイル名（キー）を取得
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
    
    print(f"処理開始: s3://{bucket}/{key}")

    try:
        # S3からアップロードされたファイルを取得
        response = s3.get_object(Bucket=bucket, Key=key)
        
        # ファイルの内容を読み込み、UTF-8でデコードして行ごとに分割
        lines = response['Body'].read().decode('utf-8').splitlines()
        
        # CSVのヘッダーをキーとする辞書として各行を読み込む
        reader = csv.DictReader(lines)

        # CSVの各行をループ処理
        for row in reader:
            try:
                # 必要なパラメータをCSVから取得
                ami_id = row.get('ami_id')
                instance_type = row.get('instance_type')
                subnet_id = row.get('subnet_id')

                # 必須項目が欠けている行はスキップ
                if not all([ami_id, instance_type, subnet_id]):
                    print(f"必須項目が不足しているためスキップします: {row}")
                    continue

                print(f"EC2インスタンスを作成します: AMI={ami_id}, Type={instance_type}, Subnet={subnet_id}")

                # EC2インスタンスを作成
                instance_response = ec2.run_instances(
                    ImageId=ami_id,
                    InstanceType=instance_type,
                    SubnetId=subnet_id,
                    MinCount=1,
                    MaxCount=1,
                    # インスタンスに自動でタグを付与する設定
                    TagSpecifications=[{
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'Name', 'Value': f'auto-created-from-{os.path.basename(key)}'},
                            {'Key': 'SourceFile', 'Value': f's3://{bucket}/{key}'}
                        ]
                    }]
                )
                
                instance_id = instance_response['Instances'][0]['InstanceId']
                print(f"インスタンス作成成功: {instance_id}")

            except Exception as e:
                # 行単位でのエラー処理
                print(f"エラーが発生したため、この行の処理を中断します: {row}, エラー: {e}")

    except Exception as e:
        # ファイル取得や全体的なエラー処理
        print(f"致命的なエラーが発生しました: {e}")
        raise e

    print(f"処理完了: s3://{bucket}/{key}")
    return {'status': 'success'}
