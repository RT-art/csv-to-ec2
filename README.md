# シンプルEC2自動作成システム

S3にCSVファイルをアップロードするだけで、EC2インスタンスを自動的に作成するシンプルなサーバーレスアプリケーションです。

## 📋 概要

AWS SAMを使い、VPCネットワーク、S3バケット、Lambda関数を一度にデプロイします。
デプロイ後、指定のS3バケットにEC2の設定情報を記述したCSVファイルをアップロードすると、Lambdaがそれを検知してEC2インスタンスを自動で作成します。

## 🛠️ 必要なもの

- AWSアカウント
- [AWS CLI](https://aws.amazon.com/jp/cli/)
- [AWS SAM CLI](https://aws.amazon.com/jp/serverless/sam/)

## 🚀 デプロイ手順

1.  **SAMアプリケーションのビルド**

    プロジェクトのルートディレクトリで以下のコマンドを実行します。
    ```bash
    sam build
    ```

2.  **ガイド付きデプロイ**

    以下のコマンドを実行し、表示される質問に答えていきます。ほとんどはデフォルトのままで問題ありません。

    ```bash
    sam deploy --guided
    ```

    **設定例:**
    - **Stack Name**: `simple-ec2-creator` (任意のスタック名)
    - **AWS Region**: `ap-northeast-1` (任意のリージョン)
    - **Confirm changes before deploy**: `y`
    - **Allow SAM CLI IAM role creation**: `y`
    - **Save arguments to samconfig.toml**: `y`

    デプロイが完了すると、`Outputs`セクションに **S3BucketName** と **PublicSubnetId** が表示されます。この2つの値を控えておいてください。

## ⚙️ 使い方

1.  **`sample.csv` を編集**

    `sample.csv` を開き、`subnet_id` の列を、デプロイ完了時に表示された `PublicSubnetId` の値に書き換えます。必要に応じて `ami_id` や `instance_type` も変更してください。

2.  **S3バケットへアップロード**

    編集したCSVファイルを、デプロイ完了時に表示された `S3BucketName` のバケットにアップロードします。

    ```bash
    # <YOUR-BUCKET-NAME> と <YOUR-SUBNET-ID> を実際の値に置き換えてください
    # 例: aws s3 cp sample.csv s3://csv-to-ec2-123456789012-ap-northeast-1/
    
    aws s3 cp sample.csv s3://<YOUR-BUCKET-NAME>/
    ```

3.  **確認**

    アップロード後、数分でLambda関数が実行され、EC2インスタンスが作成されます。AWSマネジメントコンソールのEC2ダッシュボードで確認してください。

## 🗑️ クリーンアップ

作成したすべてのリソースを削除するには、以下のコマンドを実行します。

```bash
# samconfig.tomlで設定したスタック名を指定
sam delete
