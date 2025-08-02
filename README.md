# CSV to EC2 Creator

S3へのCSVファイルアップロードをトリガーに、EC2インスタンスを自動プロビジョニングするサーバーレスアプリケーションです。

![Architecture Diagram](images/csv-to-ec2.png)

## ✨ Features

- **Infrastructure as Code (IaC)**: AWS SAM を利用してインフラストラクチャをコードで管理。
- **イベント駆動アーキテクチャ**: S3イベント通知でLambdaをトリガーする効率的な設計。
- **自動化**: CSVファイルを用意するだけで、手動でのコンソール操作なしにEC2を構築。

## 🛠️ Prerequisites

- AWSアカウント
- [AWS CLI](https://aws.amazon.com/cli/)
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
- EC2インスタンスをデプロイしたい既存のVPCとサブネット

## 🚀 Deployment

S3バケット、Lambda関数、および関連するIAMロールをデプロイします。

```bash
# SAMアプリケーションをビルド
sam build

# ガイドに従ってデプロイを実行
sam deploy --guided
```

`sam deploy --guided` の実行中、以下の項目を設定します。
- **Stack Name**: `csv-to-ec2-app-stack` など任意の名前
- **AWS Region**: `ap-northeast-1` など
- **Confirm changes before deploy**: `y`
- **Allow SAM CLI IAM role creation**: `y`
- **Disable rollback**: `y`
- **Save arguments to configuration file**: `y`

デプロイが完了すると、アウトプットに `S3BucketName` が表示されます。このS3バケットにCSVファイルをアップロードします。

## ⚙️ Usage

### 1. Prepare CSV File

プロビジョニングしたいEC2インスタンスの情報をCSVファイルに記述します。ヘッダーは `subnet_id`, `ami_id`, `instance_type` としてください。

**`instances.csv` の例:**
```csv
subnet_id,ami_id,instance_type
subnet-xxxxxxxxxxxxxxxxx,ami-0c55b159cbfafe1f0,t2.micro
subnet-xxxxxxxxxxxxxxxxx,ami-0c55b159cbfafe1f0,t3.small
```
- `subnet_id`: ご自身のAWS環境に存在する、EC2をデプロイしたいサブネットのIDを指定します。
- `ami_id`: 使用するリージョンに合ったAMI IDを指定してください (例: 東京リージョンのAmazon Linux 2023)。

### 2. Upload CSV to S3

作成したCSVファイルを、`sam deploy`で作成されたS3バケットにアップロードします。

```bash
# <YOUR-BUCKET-NAME> は sam deploy のアウトプットで確認したバケット名に置き換えてください
aws s3 cp instances.csv s3://<YOUR-BUCKET-NAME>/
```

アップロード後、Lambda関数が自動的にトリガーされ、CSVの内容に基づいてEC2インスタンスが作成されます。

---

## (Optional) Create a New Network Environment

EC2をデプロイするためのVPCやサブネットがない場合は、付属のCloudFormationテンプレートを使って新しいネットワーク環境を構築できます。

```bash
aws cloudformation deploy \
  --template-file awsnetwork.yaml \
  --stack-name csv-to-ec2-network-stack \
  --parameter-overrides VpcCidr=10.0.0.0/16 PrivateSubnetCidr=10.0.1.0/24
```

デプロイ完了後、以下のコマンドで `PrivateSubnetId` を取得し、CSVファイルに記述してください。

```bash
aws cloudformation describe-stacks \
  --stack-name csv-to-ec2-network-stack \
  --query "Stacks[0].Outputs[?OutputKey=='PrivateSubnetId'].OutputValue" \
  --output text
```

---

## 🗑️ Cleanup

デプロイしたリソースを削除するには、以下のコマンドを実行します。

```bash
# アプリケーションスタックの削除
sam delete --stack-name csv-to-ec2-app-stack

# (Optional) ネットワークスタックを作成した場合のみ実行
aws cloudformation delete-stack --stack-name csv-to-ec2-network-stack
```

## 📄 Infrastructure as Code

このプロジェクトは、以下のテンプレートによって定義されています。

- `template.yaml`: S3バケット、Lambda関数、IAMロールなど、アプリケーションのコアロジックを定義するAWS SAMテンプレート。
- `awsnetwork.yaml`: (オプション) VPC、サブネットなどの基本的なネットワークインフラを定義するCloudFormationテンプレート.