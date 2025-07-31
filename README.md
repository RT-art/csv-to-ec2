# 高セキュアなEC2自動プロビジョニングシステム

## 概要

CSVファイルをS3バケットにアップロードするだけで、AWS上に**セキュリティを考慮したプライベートなEC2インスタンス**を自動的に構築、更新、削除できるシステムです。

単にEC2を作成するだけでなく、AWSのベストプラクティスに基づき、IAMの権限分離、閉域網からのセキュアなアクセス、コードによるインフラ管理（IaC）など、実務で求められる多くの要素を盛り込んでいます。このリポジトリは、モダンなAWS環境の設計、構築、運用のスキルを証明するためのポートフォリオです。

## ✨ 主な特徴・アピールポイント

このプロジェクトは、以下の技術的な特徴を持っています。

* **サーバーレスアーキテクチャ**: S3イベントをトリガーにLambdaを起動。管理サーバー不要で、コスト効率とスケーラビリティに優れています。
* **Infrastructure as Code (IaC)**: すべてのAWSリソースをCloudFormationでコード化。インフラの再現性とバージョン管理を徹底しています。
* **高度なセキュリティ設計**:
    * **閉域網構成**: EC2インスタンスはインターネットから隔離されたプライベートサブネットに配置。
    * **SSMセッションマネージャー**: SSHキーや踏み台サーバーを必要とせず、IAMを通じてセキュアにインスタンスへアクセス。
    * **VPCエンドポイント**: NATゲートウェイを使わずに、プライベートサブネットからAWSサービス（SSM）へセキュアに接続。
* **最小権限の原則**:
    * **権限の分離**: Lambdaの実行ロールと、CloudFormationがリソースを作成するサービスロールを完全に分離。Lambdaの持つ権限を最小限に抑制しています。
* **柔軟なライフサイクル管理**:
    * CSVの内容にもとづき、EC2スタックの**作成・更新・削除**に対応。
    * インスタンスタイプやタグなどのパラメータをCSVで動的に設定可能。

## 構成図

*(ここに、新しい構成（Private Subnet, VPC Endpoints等）を反映したアーキテクチャ図を挿入してください)*

<p align="center">
  <img src="./images/architecture.png" alt="architecture" width="80%">
</p>

## 処理の流れ

1.  **CSVアップロード**: ユーザーがインスタンスの仕様を記述したCSVファイルをS3にアップロードします。
2.  **Lambda起動**: S3イベント（オブジェクト作成）をトリガーに、Lambda関数が自動的に起動します。
3.  **パラメータ解析**: LambdaはCSVファイルの中身を解析します。
    * `Action: delete`が指定されていれば、対応するCloudFormationスタックの削除処理に進みます。
    * それ以外の場合は、作成・更新処理に進みます。
4.  **スタックの存在確認**: CloudFormationの`DescribeStacks`APIを呼び出し、対応するスタックが既に存在するか確認します。
5.  **スタック操作の実行**:
    * **存在しない場合**: `CreateStack` APIを呼び出し、新しいスタックを作成します。この際、EC2作成権限を持つ**CloudFormationサービスロール**を指定します。
    * **存在する場合**: `UpdateStack` APIを呼び出し、既存のスタックを更新します。
6.  **EC2インスタンス構築**: CloudFormationが、EC2テンプレート（`ec2-template.yaml`）に基づいて、プライベートサブネット内にEC2インスタンスと関連リソース（セキュリティグループ等）を構築します。
7.  **セキュアなアクセス**: ユーザーはSSMセッションマネージャーを経由して、安全にEC2インスタンスに接続します。

## 使い方

### 事前準備

* AWSアカウント
* AWS CLI （v2推奨）
* `aws configure`による認証情報の設定

### 環境構築手順

このシステム自体もすべてCloudFormationで構築します。以下の順番でスタックをデプロイしてください。

1.  **VPCの作成**:
    ```bash
    aws cloudformation deploy --template-file vpc-template.yaml --stack-name vpc-for-csv-to-ec2
    ```
2.  **CloudFormationサービスロールの作成**:
    ```bash
    aws cloudformation deploy --template-file cfn-service-role-template.yaml --stack-name cfn-service-role-stack --capabilities CAPABILITY_NAMED_IAM
    ```
3.  **Lambda実行ロールの作成**:
    ```bash
    aws cloudformation deploy --template-file lambda-role-template.yaml --stack-name csv-to-ec2-lambda-role-stack --capabilities CAPABILITY_IAM
    ```
4.  **Lambda関数の作成**: (`[YOUR_S3_BUCKET_NAME]`はコードを置くS3バケット名に置き換えてください)
    ```bash
    aws cloudformation deploy --template-file lambda-function-template.yaml --stack-name lambda-function-stack --parameter-overrides S3BucketName=[YOUR_S3_BUCKET_NAME] S3Key=lambda_function.zip --capabilities CAPABILITY_IAM
    ```
5.  **トリガー用S3バケットの作成**: (`[LAMBDA_FUNCTION_ARN]`はステップ4で作成したLambdaのARNに置き換えてください)
    ```bash
    aws cloudformation deploy --template-file s3-bucket-template.yaml --stack-name s3-trigger-bucket-stack --parameter-overrides LambdaFunctionArn=[LAMBDA_FUNCTION_ARN]
    ```
6.  **必要ファイルのS3アップロード**:
    * `lambda_function.py`をzip化（`lambda_function.zip`）し、S3バケットにアップロードします。
    * `ec2-template.yaml`と`ami_manifest.json`をS3バケットにアップロードします。

### 実行手順

1.  **`sample.csv`を編集する**:
    作成したいEC2の情報を記述します。`Tag-`で始まるキーはEC2のタグになります。
    ```csv
    InstanceType,t2.micro
    AmiName,test
    VpcId,vpc-xxxxxxxxxxxxxxxxx
    SubnetId,subnet-xxxxxxxxxxxxxxxxx
    SshAccessCidr,0.0.0.0/0
    Tag-Name,My-Secure-EC2
    Tag-Project,Portfolio
    ```
2.  **CSVをS3にアップロードする**: (`[YOUR_S3_BUCKET_NAME]`はご自身のバケット名に置き換えてください)
    ```bash
    aws s3 cp sample.csv s3://[YOUR_S3_BUCKET_NAME]/
    ```
3.  **EC2への接続**:
    * AWSコンソールでEC2インスタンスを選択し、「接続」→「セッションマネージャー」経由で接続します。
    * またはCLIで `aws ssm start-session --target [インスタンスID]` を実行します。

## 使用技術

* **AWS**
    * AWS Lambda
    * Amazon S3
    * AWS CloudFormation
    * Amazon VPC (VPC Endpoint)
    * Amazon EC2
    * AWS IAM
    * AWS Systems Manager (SSM) Session Manager
    * Amazon CloudWatch Logs
* **言語・その他**
    * Python 3.11
    * Boto3
    * YAML
    * AWS CLI