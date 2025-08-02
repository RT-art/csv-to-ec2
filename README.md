CSV to EC2 Creator
S3にアップロードされたCSVファイルの内容に基づき、EC2インスタンスを自動的にプロビジョニングするプロジェクトです。

概要
このプロジェクトは、AWSのサーバーレスアーキテクチャを活用し、手動でのインスタンス作成作業を自動化します。指定されたフォーマットのCSVファイルをS3バケットにアップロードするだけで、S3イベント通知がLambda関数をトリガーし、CSVに定義されたパラメータ（インスタンスタイプ、AMIなど）を持つEC2インスタンスが自動で構築されます。

インフラの定義にはAWS SAM (Serverless Application Model) を使用しており、IaC (Infrastructure as Code) によって管理されています。

アーキテクチャ
全体像は以下の通りです。

CSV Upload: ユーザーがローカル環境から設定を記述したCSVファイルをS3バケットにアップロードします。

S3 Event Notification: S3バケットはオブジェクト作成イベントを検知し、Lambda関数を非同期で呼び出します。

Lambda Execution: Lambda関数がトリガーされ、アップロードされたCSVファイルを取得・解析します。

EC2 Provisioning: Lambda関数はboto3ライブラリを使用し、CSVの各行で定義されたパラメータに基づいてEC2インスタンスを作成します。

使用方法
前提条件
AWSアカウント

AWS SAM CLI

デプロイ
リポジトリをクローンします。

Bash

git clone <repository-url>
cd csv-to-ec2
SAMアプリケーションをビルドします。

Bash

sam build
ガイドに従ってデプロイを実行します。

Bash

sam deploy --guided
CSVファイルのフォーマット
S3にアップロードするCSVファイルは、以下のヘッダーを持つ必要があります。

コード スニペット

subnet_id,ami_id,instance_type
subnet-xxxxxxxx,ami-zzzzzzzz,t2.micro
subnet-yyyyyyyy,ami-aaaaaaaa,t3.small
クリーンアップ
デプロイしたリソースを削除するには、以下のコマンドを実行します。

Bash

sam delete