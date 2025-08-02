CSV-to-EC2 Orchestrator
S3にCSVファイルをアップロードするだけで、EC2インスタンスのプロビジョニングからセットアップまでを自動実行する、サーバーレスなオーケストレーションシステムです。

<p align="center">
<img src="images/architecture_stepfunctions.png" alt="architecture" width="90%">
<br>
<em>(新しいアーキテクチャ図をここに配置)</em>
</p>

✨ 概要
このプロジェクトは、CSVファイルに定義された情報に基づき、EC2インスタンスを自動で構築・設定します。AWS Step Functions を中心に、モダンなクラウドネイティブのベストプラクティスをふんだんに取り入れた、堅牢でスケーラブルな設計が特徴です。

主な特徴
サーバーレス & イベント駆動: S3へのアップロードをトリガーに、すべてのプロセスが自動的に開始されます。

オーケストレーション: AWS Step Functions を利用し、CloudFormationの実行、完了待機、後続処理（SSMコマンド実行）といった一連のワークフローを確実かつ視覚的に管理します。

IaC (Infrastructure as Code): AWS SAM を用いて、ネットワーク、IAMロール、Lambda関数、Step Functionsステートマシンなど、すべてのリソースをコードで宣言的に管理します。

堅牢性と信頼性: Step Functionsによるリトライ・エラーハンドリング、べき等性を担保した設定スクリプトにより、信頼性の高い処理を実現します。

疎結合な設計: 各コンポーネントが単一の責務を持ち、疎に結合しているため、保守性と拡張性に優れています。

⚙️ アーキテクチャ
ユーザーがCSVファイルをS3バケットにアップロードします。

S3イベントがLambda関数（StartWorkflowFunction）をトリガーします。

LambdaはCSVの各行の情報をペイロードとして、Step Functionsのワークフローを開始します。

Step Functionsは以下のワークフローを順次実行します。
a.  CloudFormationスタックを作成・更新し、完了まで待機します。
b.  別のLambda関数（GetStackOutputFunction）を呼び出し、作成されたEC2のインスタンスIDを取得します。
c.  取得したインスタンスIDに対し、SSM Run CommandでDockerのインストールなど初期設定を実行します。

エラーが発生した場合は、ワークフローが自動的に失敗状態となり、AWSコンソールから原因を簡単に特定できます。

🛠️ セットアップとデプロイ
要件
AWS CLI

AWS SAM CLI

Python 3.11

Docker (SAMのローカルテスト用)

デプロイ手順
Bash

# 1. リポジトリをクローン
git clone https://github.com/YOUR_USERNAME/csv-to-ec2.git
cd csv-to-ec2

# 2. ネストスタック用のテンプレートをS3にアップロード
# (事前にS3バケットを作成しておく必要があります)
aws s3 cp ec2-template.yaml s3://<YOUR-BUCKET-NAME>/ec2-template.yaml

# 3. アプリケーションをビルド
sam build

# 4. ガイドに従ってデプロイ
sam deploy --guided
使い方
CSVファイルの作成:
StackName, Action, InstanceType, AmiId などのヘッダーを持つCSVファイルを作成します。

sample.csv

コード スニペット

StackName,Action,InstanceType,AmiId
ec2-web-01,create,t2.micro,ami-0c55b159cbfafe1f0
ec2-db-01,create,t3.small,ami-0c55b159cbfafe1f0
S3へアップロード:
デプロイ時に作成されたS3バケットに、作成したCSVファイルをアップロードします。

Bash

aws s3 cp sample.csv s3://<YOUR-DEPLOYED-BUCKET-NAME>/
アップロード後、自動的にStep Functionsのワークフローが実行されます。実行状況はAWSマネジメントコンソールのStep Functionsのページから視覚的に確認できます。