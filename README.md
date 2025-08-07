# サーバーレスEC2プロビジョニング from CSV ✨

S3にアップロードされたCSVファイルに基づき、EC2インスタンスを自動で作成するAWS SAMアプリケーションです。

管理スクリプト (`manage.sh`) を利用することで、AWSリソースのデプロイからインスタンス作成のトリガーとなるファイルアップロードまで、簡単なコマンドで実行できます。作成されるすべてのEC2インスタンスには、**デフォルトでSSM（AWS Systems Manager）が有効化**されます。

## 🏛️ アーキテクチャ

![アーキテクチャ図](images/アーキテクチャ図.png)

1.  ユーザーが `manage.sh upload` コマンドでCSVファイルをS3バケットにアップロードします。
2.  S3へのファイルアップロードをトリガーとして、Lambda関数が実行されます。
3.  Lambda関数はCSVファイルの内容を読み取ります。
4.  CSVの各行で指定されたAMI IDとインスタンスタイプに基づき、EC2インスタンスを作成します。
5.  作成されるすべてのインスタンスには、SSM接続を許可するIAMロールがアタッチされます。

## 🚀 使い方

**前提条件:**

  - [AWS CLI](https://aws.amazon.com/cli/) と [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html) がインストール済みであること。
  - AWS認証情報が設定済みであること (`aws configure`)。

-----

### **Step 1: デプロイ (初回のみ)**

最初に、AWS環境に必要なリソース一式（VPC, S3バケット, Lambda関数など）をデプロイします。この操作は一度だけ行います。

1.  スクリプトに実行権限を付与します。

    ```bash
    chmod +x manage.sh
    ```

2.  デプロイコマンドを実行します。

    ```bash
    ./manage.sh deploy
    ```

    CloudFormationスタックの作成が完了すれば、環境の準備は完了です。

-----

### **Step 2: EC2インスタンスの作成**

1.  **CSVファイルを用意します。**
    `sample.csv` を参考に、作成したいEC2インスタンスの情報を記述します。

      - **`ami_id`** と **`instance_type`** の列は**必須**です。

    **`sample.csv` の例:**

    ```csv
    ami_id,instance_type
    ami-0abcdef1234567890,t2.micro
    ami-0abcdef1234567890,t3.small
    ```

2.  **CSVファイルをアップロードしてインスタンスを作成します。**
    `upload` コマンドを実行すると、Lambda関数がトリガーされ、CSVの内容に基づいてEC2インスタンスが自動で作成されます。

      - **【推奨】単一のCSVファイルを自動検出**
        カレントディレクトリにCSVファイルが1つだけ存在する場合、ファイル名を指定しなくても自動で検知してアップロードします。

        ```bash
        # カレントディレクトリにある唯一の.csvファイルをアップロード
        ./manage.sh upload
        ```

      - **特定のファイルを指定**
        複数のCSVファイルがある場合や、特定のファイルを指定したい場合は、ファイル名を引数として渡します。

        ```bash
        # my_instances.csv を指定してアップロード
        ./manage.csv upload my_instances.csv
        ```

-----

### **Step 3: クリーンアップ 🗑️**

このアプリケーションで作成したすべてのAWSリソースを削除するには、以下のコマンドを実行します。

```bash
./manage.sh delete
```

VPC、S3バケット、Lambda関数、IAMロールなど、関連リソースが一括で削除されます。
