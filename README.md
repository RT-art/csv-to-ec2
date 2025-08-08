# CSV-TO-EC2

S3にアップロードされたCSVに基づき、EC2インスタンスを自動で作成します。

![アーキテクチャ図](images/アーキテクチャ図.png)

## 必須ツール

  * [AWS CLI](https://aws.amazon.com/cli/)
  * [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)

## Usage

### **1. 初期設定 (初回のみ)**

```bash
# 認証情報を設定
aws configure

# スクリプトに実行権限を付与
chmod +x manage.sh
```

-----

### **2. デプロイ**

AWS上に必要なリソース（VPC, S3, Lambda等）を作成します。

```bash
./manage.sh deploy
```

-----

### **3. EC2インスタンスの作成**

`sample.csv` を編集し、作成したいインスタンスの`ami_id`と`instance_type`を記述します。

**`sample.csv` の例:**

```csv
ami_id,instance_type
ami-0abcdef1234567890,t2.micro
ami-0abcdef1234567890,t3.small
```

その後、以下のコマンドでCSVをアップロードし、インスタンス作成をトリガーします。

```bash
# カレントディレクトリのCSVを自動でアップロード
./manage.sh upload

# ファイル名を指定してアップロード
./manage.sh upload sample.csv
```

-----

### **4. クリーンアップ**

作成したすべてのAWSリソースを削除します。

```bash
./manage.sh delete
