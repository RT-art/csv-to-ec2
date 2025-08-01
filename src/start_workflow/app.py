import json
import os
import boto3
import csv
import codecs
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
stepfunctions_client = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')
REQUIRED_COLUMNS = ['StackName', 'Action', 'InstanceType', 'AmiId']

def lambda_handler(event, context):
    """
    S3にアップロードされたCSVファイルを読み取り、各行のデータに基づいて
    Step Functionsのワークフローを開始する。
    """
    if not STATE_MACHINE_ARN:
        print("Fatal: STATE_MACHINE_ARN environment variable is not set.")
        return {'statusCode': 500, 'body': 'Service misconfiguration.'}

    try:
        bucket_name = event['Records'][0]['s3']['bucket']['name']
        file_key = event['Records'][0]['s3']['object']['key']
    except (KeyError, IndexError):
        print("Error: Not a valid S3 event.")
        return {'statusCode': 400, 'body': 'Not a valid S3 event.'}

    print(f"Processing file: s3://{bucket_name}/{file_key}")

    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        csv_reader = csv.DictReader(codecs.getreader('utf-8')(response['Body']))
        
        executions = []
        for i, row in enumerate(csv_reader, 1):
            # 必須カラムの存在チェック
            missing_cols = [col for col in REQUIRED_COLUMNS if col not in row or not row[col]]
            if missing_cols:
                print(f"Skipping row {i}: Missing required columns - {', '.join(missing_cols)}")
                continue

            # 入力から空の値を削除
            payload = {k: v for k, v in row.items() if v}
            
            print(f"Starting Step Functions execution for row {i}: {payload}")
            
            # Step Functions の実行を開始
            exec_response = stepfunctions_client.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                input=json.dumps({"Input": payload})
            )
            executions.append(exec_response['executionArn'])

        print(f"Successfully started {len(executions)} executions.")
        return {'statusCode': 200, 'body': json.dumps(executions)}

    except ClientError as e:
        print(f"AWS Client Error: {e}")
        return {'statusCode': 500, 'body': str(e)}
    except Exception as e:
        print(f"Internal Error: {e}")
        return {'statusCode': 500, 'body': str(e)}