import boto3
import csv
import os

s3_client = boto3.client('s3')
cfn_client = boto3.client('cloudformation')

def lambda_handler(event, context):
    try:
        bucket_name = event['Records'][0]['s3']['bucket']['name']
        file_key = event['Records'][0]['s3']['object']['key']
        
        print(f"Processing file: s3://{bucket_name}/{file_key}")

        response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        csv_content = response['Body'].read().decode('utf-8').splitlines()
        
        csv_reader = csv.reader(csv_content)
        params = []
        for row in csv_reader:
            if len(row) == 2:
                params.append({'ParameterKey': row[0], 'ParameterValue': row[1]})
        
        print(f"Parameters from CSV: {params}")

        stack_name = f"{os.path.splitext(file_key)[0]}-stack"
        
        template_url = "https://rt-ec2-to-csv-bucket.s3.ap-northeast-1.amazonaws.com/ec2-template.yaml"
        
        print(f"Creating CloudFormation stack: {stack_name}")
        
        cfn_client.create_stack(
            StackName=stack_name,
            TemplateURL=template_url,
            Parameters=params,
            Capabilities=['CAPABILITY_IAM']
        )
        
        print("Stack creation initiated successfully.")
        return {'statusCode': 200, 'body': 'Success'}

    except Exception as e:
        print(f"Error: {e}")
        return {'statusCode': 500, 'body': f'Error: {e}'}
