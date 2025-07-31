import boto3
import csv
import os
import json
from botocore.exceptions import ClientError # エラーハンドリングのために追加

s3_client = boto3.client('s3')
cfn_client = boto3.client('cloudformation')

MANIFEST_FILE_KEY = 'ami_manifest.json'
# 環境変数からサービスロールARNを取得
CFN_SERVICE_ROLE_ARN = os.environ.get('CFN_SERVICE_ROLE_ARN')

def get_ami_id_from_manifest(bucket, ami_name):
    try:
        manifest_obj = s3_client.get_object(Bucket=bucket, Key=MANIFEST_FILE_KEY)
        manifest_content = manifest_obj['Body'].read().decode('utf-8')
        ami_catalog = json.loads(manifest_content)
        for category, images in ami_catalog.items():
            if ami_name in images:
                return images[ami_name]['ami_id']
        raise ValueError(f"AmiName '{ami_name}' not found in any category in the manifest file.")
    except s3_client.exceptions.NoSuchKey:
        raise FileNotFoundError(f"Manifest file '{MANIFEST_FILE_KEY}' not found in bucket '{bucket}'.")
    except Exception as e:
        print(f"Error processing manifest file: {e}")
        raise

def lambda_handler(event, context):
    # --- サービスロールが設定されているか最初にチェック ---
    if not CFN_SERVICE_ROLE_ARN:
        print("Fatal Error: CFN_SERVICE_ROLE_ARN environment variable not set.")
        return {'statusCode': 500, 'body': 'Service role not configured.'}

    try:
        if 'Records' not in event:
            return {'statusCode': 400, 'body': 'Not an S3 event.'}

        bucket_name = event['Records'][0]['s3']['bucket']['name']
        file_key = event['Records'][0]['s3']['object']['key']

        if file_key == MANIFEST_FILE_KEY:
            return {'statusCode': 200, 'body': 'Manifest file update ignored.'}

        print(f"Processing file: s3://{bucket_name}/{file_key}")
        
        stack_name = f"ec2-{os.path.splitext(file_key)[0].replace('.','-')}-stack"
        
        # CSVファイルを読み込み
        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        csv_content = response['Body'].read().decode('utf-8').splitlines()
        csv_reader = csv.reader(csv_content)
        params_dict = {row[0]: row[1] for row in csv_reader if len(row) == 2}

        # 削除処理の判定
        if params_dict.get('Action', '').lower() == 'delete':
            print(f"Deletion requested for stack: {stack_name}")
            cfn_client.delete_stack(StackName=stack_name)
            print(f"Stack {stack_name} deletion initiated.")
            return {'statusCode': 200, 'body': f"Stack {stack_name} deletion initiated."}

        params_dict_cfn = {}
        tags_list = []
        for key, value in params_dict.items():
            if key.startswith('Tag-'):
                tags_list.append({'Key': key.replace('Tag-', '', 1), 'Value': value})
            else:
                params_dict_cfn[key] = value

        if 'AmiName' in params_dict_cfn:
            ami_name = params_dict_cfn.pop('AmiName')
            ami_id = get_ami_id_from_manifest(bucket_name, ami_name)
            params_dict_cfn['AmiId'] = ami_id
        
        params_list = [{'ParameterKey': k, 'ParameterValue': v} for k, v in params_dict_cfn.items()]
        
        print(f"Parameters for CloudFormation: {params_list}")
        print(f"Tags for CloudFormation: {tags_list}")
        
        template_url = f"https://{bucket_name}.s3.ap-northeast-1.amazonaws.com/ec2-template.yaml"

        # スタックが存在するか確認し、存在すれば更新、なければ作成 (Upsert)
        try:
            cfn_client.describe_stacks(StackName=stack_name)
            print(f"Stack {stack_name} exists. Updating stack...")
            cfn_client.update_stack(
                StackName=stack_name,
                TemplateURL=template_url,
                Parameters=params_list,
                Tags=tags_list,
                RoleARN=CFN_SERVICE_ROLE_ARN # ← サービスロールを指定
            )
            print(f"Stack {stack_name} update initiated.")
        except ClientError as e:
            if "does not exist" in e.response['Error']['Message']:
                print(f"Stack {stack_name} does not exist. Creating stack...")
                cfn_client.create_stack(
                    StackName=stack_name,
                    TemplateURL=template_url,
                    Parameters=params_list,
                    Tags=tags_list,
                    RoleARN=CFN_SERVICE_ROLE_ARN # ← サービスロールを指定
                )
                print(f"Stack {stack_name} creation initiated.")
            else:
                raise 

        return {'statusCode': 200, 'body': 'Success'}

    except (ValueError, FileNotFoundError) as e:
        print(f"Configuration Error: {e}")
        return {'statusCode': 400, 'body': f"Configuration Error: {e}"}
    except ClientError as e:    
        if "No updates are to be performed" in e.response['Error']['Message']:
            print("No changes detected. Stack update skipped.")
            return {'statusCode': 200, 'body': 'No updates to be performed.'}
        print(f"AWS Client Error: {e}")
        return {'statusCode': 500, 'body': f"AWS Client Error: {e}"}
    except Exception as e:
        print(f"Internal Error: {e}")
        return {'statusCode': 500, 'body': f"Internal Error: {e}"}