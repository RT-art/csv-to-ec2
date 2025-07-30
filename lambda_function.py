import boto3
import csv
import os
import json

s3_client = boto3.client('s3')
cfn_client = boto3.client('cloudformation')

MANIFEST_FILE_KEY = 'ami_manifest.json'

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
    try:
        if 'Records' not in event:
            print("This function is intended to be triggered by S3 events.")
            return {'statusCode': 400, 'body': 'Not an S3 event.'}

        bucket_name = event['Records'][0]['s3']['bucket']['name']
        file_key = event['Records'][0]['s3']['object']['key']

        if file_key == MANIFEST_FILE_KEY:
            print(f"Ignoring manifest file update: {file_key}")
            return {'statusCode': 200, 'body': 'Manifest file update ignored.'}

        print(f"Processing file: s3://{bucket_name}/{file_key}")

        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        csv_content = response['Body'].read().decode('utf-8').splitlines()
        csv_reader = csv.reader(csv_content)
        
        params_dict = {}
        tags_list = []
        for row in csv_reader:
            if len(row) == 2:
                key, value = row[0], row[1]
                if key.startswith('Tag-'):
                    tag_key = key.replace('Tag-', '', 1)
                    tags_list.append({'Key': tag_key, 'Value': value})
                else:
                    params_dict[key] = value

        if 'AmiName' in params_dict:
            ami_name = params_dict.pop('AmiName')
            ami_id = get_ami_id_from_manifest(bucket_name, ami_name)
            params_dict['AmiId'] = ami_id
        
        params_list = [{'ParameterKey': k, 'ParameterValue': v} for k, v in params_dict.items()]
        
        print(f"Parameters for CloudFormation: {params_list}")
        print(f"Tags for CloudFormation: {tags_list}") # タグをログに出力

        stack_name = f"ec2-{os.path.splitext(file_key)[0].replace('.','-')}-stack"
        template_url = f"https://{bucket_name}.s3.ap-northeast-1.amazonaws.com/ec2-template.yaml"
        
        print(f"Creating CloudFormation stack: {stack_name}")
        
        cfn_client.create_stack(
            StackName=stack_name,
            TemplateURL=template_url,
            Parameters=params_list,
            Tags=tags_list  # ← create_stackにTagsパラメータを渡す
        )
        
        print("Stack creation initiated successfully.")
        return {'statusCode': 200, 'body': 'Success'}

    except (ValueError, FileNotFoundError) as e:
        print(f"Configuration Error: {e}")
        return {'statusCode': 400, 'body': f"Configuration Error: {e}"}
    except Exception as e:
        print(f"Internal Error: {e}")
        return {'statusCode': 500, 'body': f"Internal Error: {e}"}