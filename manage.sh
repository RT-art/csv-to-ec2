#!/bin/bash

# A script to manage the deployment and usage of the csv-to-ec2 SAM application.

# Stop script on any error
set -e

# --- Configuration ---
# File to store the outputs from the SAM deployment, like the S3 bucket name.
CONFIG_FILE=".sam_outputs"
STACK_NAME="csv-to-ec2-stack" # You can change this default stack name
REGION=$(aws configure get region)
[ -z "$REGION" ] && REGION="ap-northeast-1" # Default to Tokyo if not set

# --- Helper Functions ---
# Print usage instructions
usage() {
    echo "Usage: $0 {deploy|upload|delete}"
    echo
    echo "Commands:"
    echo "  deploy   : Builds and deploys the AWS SAM stack. Creates network resources, S3 bucket, and Lambda."
    echo "  upload   : Uploads a CSV file to the S3 bucket to trigger instance creation. Auto-detects a single .csv file if no argument is given."
    echo "  delete   : Deletes the entire AWS SAM stack and all created resources."
    echo
}

# --- Main Functions ---

# Build and Deploy the SAM stack
deploy_stack() {
    echo ">>> Building the SAM application..."
    sam build

    echo ">>> Deploying the stack '$STACK_NAME' to region '$REGION'..."
    sam deploy --stack-name "$STACK_NAME" --region "$REGION" --capabilities CAPABILITY_IAM --resolve-s3 --confirm-changeset

    echo ">>> Deployment successful. Fetching S3 bucket name..."
    
    # Get the S3 bucket name from the CloudFormation stack outputs
    BUCKET_NAME=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" \
        --output text \
        --region "$REGION")

    if [ -z "$BUCKET_NAME" ]; then
        echo "Error: Could not retrieve S3 bucket name from stack outputs."
        echo "Please check the AWS Management Console for the stack status."
        exit 1
    fi

    # Save the bucket name to the config file for the 'upload' command
    echo "S3_BUCKET_NAME=$BUCKET_NAME" > "$CONFIG_FILE"
    
    echo "✔ Setup complete."
    echo "  S3 Bucket '$BUCKET_NAME' is ready."
    echo "  You can now use './manage.sh upload' to create EC2 instances."
}

# Upload a CSV file to the S3 bucket
upload_csv() {
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Error: Configuration file '$CONFIG_FILE' not found."
        echo "Please run './manage.sh deploy' first to set up the environment."
        exit 1
    fi

    # Load the bucket name from the config file
    source "$CONFIG_FILE"

    if [ -z "$S3_BUCKET_NAME" ]; then
        echo "Error: S3_BUCKET_NAME not found in '$CONFIG_FILE'."
        exit 1
    fi

    local CSV_FILE
    # If an argument is given, use it as the CSV file path.
    if [ -n "$1" ]; then
        CSV_FILE="$1"
    else
        # Otherwise, try to auto-detect a single CSV file in the current directory.
        local csv_files=(*.csv) # Use a robust bash array
        local num_files=${#csv_files[@]}

        if [ "$num_files" -eq 1 ]; then
            CSV_FILE="${csv_files[0]}"
            echo ">>> Auto-detected CSV file: '$CSV_FILE'"
        elif [ "$num_files" -eq 0 ]; then
            echo "Error: No CSV file found in the current directory."
            echo "Please place a single .csv file here or specify the file path:"
            echo "  ./manage.sh upload <your-file.csv>"
            exit 1
        else
            echo "Error: Multiple CSV files found. Please specify which one to upload:"
            printf " - %s\n" "${csv_files[@]}"
            echo "Usage: ./manage.sh upload <file-to-upload.csv>"
            exit 1
        fi
    fi

    if [ ! -f "$CSV_FILE" ]; then
        echo "Error: CSV file '$CSV_FILE' not found."
        exit 1
    fi

    echo ">>> Uploading '$CSV_FILE' to bucket '$S3_BUCKET_NAME'..."
    aws s3 cp "$CSV_FILE" "s3://$S3_BUCKET_NAME/"

    echo "✔ File uploaded successfully. EC2 instance creation has been triggered."
}

# Delete the SAM stack
delete_stack() {
    echo ">>> Deleting the SAM stack '$STACK_NAME' from region '$REGION'..."
    echo "!!! This will remove all AWS resources created by this script. !!!"
    
    sam delete --stack-name "$STACK_NAME" --region "$REGION" --no-prompts

    # Clean up local config file
    if [ -f "$CONFIG_FILE" ]; then
        rm "$CONFIG_FILE"
    fi

    echo "✔ Stack deleted successfully."
}


# --- Script Entrypoint ---
# Check for required tools
if ! command -v sam &> /dev/null || ! command -v aws &> /dev/null; then
    echo "Error: 'sam' and 'aws' CLI tools are required."
    echo "Please install them and configure your AWS credentials."
    exit 1
fi


# Main command router
case "$1" in
    deploy)
        deploy_stack
        ;;
    upload)
        # Pass the second argument (the filename) to the upload function
        upload_csv "$2"
        ;;
    delete)
        delete_stack
        ;;
    *)
        usage
        exit 1
        ;;
esac

exit 0
