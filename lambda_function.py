import boto3
import csv
import os
from typing import List, Dict, Optional
import time
import codecs
from botocore.exceptions import ClientError

# Boto3 clients initialized once
s3_client = boto3.client('s3')
cfn_client = boto3.client('cloudformation')
ssm_client = boto3.client('ssm')

# Environment variables
CFN_SERVICE_ROLE_ARN = os.environ.get('CFN_SERVICE_ROLE_ARN')
EC2_TEMPLATE_URL = os.environ.get('EC2_TEMPLATE_URL')
VPC_ID = os.environ.get('VPC_ID')
SUBNET_ID = os.environ.get('SUBNET_ID')

def parse_csv_data(bucket: str, key: str) -> List[Dict[str, str]]:
    """CSVファイルを解析してディクショナリのリストを返す
    
    Args:
        bucket: S3バケット名
        key: CSVファイルのキー
        
    Returns:
        List[Dict[str, str]]: CSVの各行をディクショナリとしたリスト
        
    Raises:
        ValueError: CSVが空またはヘッダーのみの場合
    """
    response = s3_client.get_object(Bucket=bucket, Key=key)
    # Use codecs for streaming decode
    csv_reader = csv.DictReader(codecs.getreader('utf-8')(response['Body']))
    rows = list(csv_reader)
    if not rows:
        raise ValueError("CSV file is empty or contains only headers.")
    return rows

def delete_stack(stack_name):
    """Initiates deletion of a CloudFormation stack."""
    try:
        print(f"Deletion requested for stack: {stack_name}")
        cfn_client.delete_stack(StackName=stack_name)
        print(f"Stack {stack_name} deletion initiated.")
    except ClientError as e:
        if "does not exist" in e.response['Error']['Message']:
            print(f"Stack {stack_name} does not exist, nothing to delete.")
        else:
            raise

def upsert_stack(stack_name: str, parameters: List[Dict[str, str]], tags: List[Dict[str, str]]) -> None:
    """CloudFormationスタックを作成または更新
    
    Args:
        stack_name: スタック名
        parameters: CloudFormationパラメータのリスト
        tags: タグのリスト
    """
    common_args = {
        'StackName': stack_name,
        'TemplateURL': EC2_TEMPLATE_URL,
        'Parameters': parameters,
        'Tags': tags,
        'RoleARN': CFN_SERVICE_ROLE_ARN,
        'Capabilities': ['CAPABILITY_NAMED_IAM']
    }
    try:
        cfn_client.describe_stacks(StackName=stack_name)
        print(f"Stack {stack_name} exists. Updating stack...")
        cfn_client.update_stack(**common_args)
        print(f"Stack {stack_name} update initiated.")
    except ClientError as e:
        if "does not exist" in e.response['Error']['Message']:
            print(f"Stack {stack_name} does not exist. Creating stack...")
            cfn_client.create_stack(**common_args)
            print(f"Stack {stack_name} creation initiated.")
        elif "No updates are to be performed" in e.response['Error']['Message']:
            print(f"No changes detected for stack {stack_name}. Update skipped.")
        else:
            raise

def invoke_ssm_run_command(instance_id, hostname):
    """Invokes SSM Run Command to rename the Windows instance."""
    if not hostname:
        print(f"No HostName provided for instance {instance_id}. Skipping rename.")
        return

    print(f"Invoking SSM Run Command to rename instance {instance_id} to {hostname}")
    try:
        ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunPowerShellScript',
            Parameters={
                'commands': [
                    f'Rename-Computer -NewName "{hostname}" -Force -Restart'
                ]
            }
        )
        print(f"SSM command sent to instance {instance_id} successfully.")
    except ClientError as e:
        print(f"Failed to send SSM command to instance {instance_id}: {e}")

def wait_for_instance_id(stack_name: str, max_attempts: int = 8, delay: int = 15) -> Optional[str]:
    """スタックからインスタンスIDを取得（リトライ付き）
    
    Args:
        stack_name: CloudFormationスタック名
        max_attempts: 最大リトライ回数
        delay: リトライ間隔（秒）
        
    Returns:
        Optional[str]: インスタンスID。見つからない場合はNone
    """
    for i in range(max_attempts):
        try:
            stack_info = cfn_client.describe_stacks(StackName=stack_name)
            instance_id = next(
                (o['OutputValue'] for o in stack_info['Stacks'][0]['Outputs'] 
                 if o['OutputKey'] == 'InstanceId'),
                None
            )
            if instance_id:
                print(f"Found InstanceId: {instance_id}")
                return instance_id
        except ClientError:
            print(f"Attempt {i+1}: Could not describe stack yet. Retrying...")
        time.sleep(delay)
    return None

def process_csv_row(row: Dict[str, str]) -> None:
    """CSVの1行を処理してEC2インスタンスを作成または削除
    
    Args:
        row: CSVの1行のデータ
    """
    stack_name = row.get('StackName')
    if not stack_name:
        print("Skipping row due to missing 'StackName'.")
        return

    if not stack_name.startswith('ec2-'):
        print(f"StackName '{stack_name}' must start with 'ec2-'. Skipping.")
        return

    if row.get('Action', '').lower() == 'delete':
        delete_stack(stack_name)
        return

    # スタックパラメータとタグの準備
    cfn_params = [
        {'ParameterKey': 'VpcId', 'ParameterValue': VPC_ID},
        {'ParameterKey': 'SubnetId', 'ParameterValue': SUBNET_ID},
    ]
    cfn_tags = []
    
    # AMI IDとホスト名の処理
    ami_id = row.get('AmiId')
    new_hostname = row.get('HostName')
    
    if ami_id:
        cfn_params.append({'ParameterKey': 'AmiId', 'ParameterValue': ami_id})

    # その他のパラメータとタグの処理
    for key, value in row.items():
        if value:  # 空値をスキップ
            if key.lower().startswith('tag-'):
                cfn_tags.append({'Key': key[4:], 'Value': value})
            elif key not in ['Action', 'StackName', 'HostName', 'AmiId']:
                cfn_params.append({'ParameterKey': key, 'ParameterValue': value})

    # ホスト名をタグとして追加
    if new_hostname:
        cfn_tags.append({'Key': 'Name', 'Value': new_hostname})
    
    # スタックの作成/更新
    upsert_stack(stack_name, cfn_params, cfn_tags)

    # ホスト名の設定
    if new_hostname:
        print("Waiting for stack operation to progress...")
        time.sleep(20)  # 初期待機
        
        if instance_id := wait_for_instance_id(stack_name):
            invoke_ssm_run_command(instance_id, new_hostname)
        else:
            print(f"Could not find InstanceId for stack {stack_name}")

def lambda_handler(event, context):
    """S3イベントでトリガーされるメイン関数"""
    if not all([CFN_SERVICE_ROLE_ARN, EC2_TEMPLATE_URL, VPC_ID, SUBNET_ID]):
        print("Fatal: Missing one or more required environment variables.")
        return {'statusCode': 500, 'body': 'Service misconfiguration.'}

    try:
        bucket_name = event['Records'][0]['s3']['bucket']['name']
        file_key = event['Records'][0]['s3']['object']['key']
    except (KeyError, IndexError):
        return {'statusCode': 400, 'body': 'Not a valid S3 event.'}

    if not file_key.lower().endswith('.csv'):
        return {'statusCode': 200, 'body': f'Object {file_key} is not a CSV, ignoring.'}

    print(f"Processing file: s3://{bucket_name}/{file_key}")

    try:
        for row in parse_csv_data(bucket_name, file_key):
            stack_name = row.get('StackName')
            if not stack_name:
                print("Skipping row due to missing 'StackName'.")
                continue

            if not stack_name.startswith('ec2-'):
                print(f"StackName '{stack_name}' must start with 'ec2-'. Skipping.")
                continue

            # Handle delete action
            if row.get('Action', '').lower() == 'delete':
                delete_stack(stack_name)
                continue

            # Prepare CloudFormation parameters and tags
            cfn_params = [
                {'ParameterKey': 'VpcId', 'ParameterValue': VPC_ID},
                {'ParameterKey': 'SubnetId', 'ParameterValue': SUBNET_ID},
            ]
            cfn_tags = []
            new_hostname = row.get('HostName')

            # Get AmiId directly from CSV
            ami_id = row.get('AmiId')
            if ami_id:
                cfn_params.append({'ParameterKey': 'AmiId', 'ParameterValue': ami_id})

            # Process other parameters and tags from CSV
            for key, value in row.items():
                if key.lower().startswith('tag-'):
                    cfn_tags.append({'Key': key[4:], 'Value': value})
                elif key not in ['Action', 'StackName', 'HostName', 'AmiId']:
                    cfn_params.append({'ParameterKey': key, 'ParameterValue': value})

            # Add HostName as the 'Name' tag for visibility in the console
            if new_hostname:
                cfn_tags.append({'Key': 'Name', 'Value': new_hostname})
            
            # Upsert the stack
            upsert_stack(stack_name, cfn_params, cfn_tags)

            # Wait and then run SSM command
            if new_hostname:
                print("Waiting for stack operation to progress before fetching InstanceId...")
                time.sleep(20) # Wait for stack creation/update to begin
                
                instance_id = None
                for i in range(8): # Retry for up to ~2 minutes
                    try:
                        stack_info = cfn_client.describe_stacks(StackName=stack_name)
                        instance_id = next(
                            (o['OutputValue'] for o in stack_info['Stacks'][0]['Outputs'] if o['OutputKey'] == 'InstanceId'),
                            None
                        )
                        if instance_id:
                            print(f"Found InstanceId: {instance_id}")
                            break
                    except ClientError:
                        print(f"Attempt {i+1}: Could not describe stack yet. Retrying...")
                    time.sleep(15)

                if instance_id:
                    invoke_ssm_run_command(instance_id, new_hostname)
                else:
                    print(f"Could not find InstanceId for stack {stack_name} after multiple attempts.")
        
        return {'statusCode': 200, 'body': 'Processing complete.'}

    except (ValueError, FileNotFoundError) as e:
        print(f"Configuration Error: {e}")
        return {'statusCode': 400, 'body': str(e)}
    except ClientError as e:
        print(f"AWS Client Error: {e}")
        return {'statusCode': 500, 'body': str(e)}
    except Exception as e:
        print(f"Internal Error: {e}")
        return {'statusCode': 500, 'body': str(e)}