#!/bin/bash

# csv-to-ec2 SAMアプリケーションのデプロイと管理を行うスクリプト

# エラー発生時にスクリプトを停止
set -e

# --- 設定 ---
# SAMデプロイのアウトプット（S3バケット名など）を保存するファイル
CONFIG_FILE=".sam_outputs"

# CloudFormationのスタック名
STACK_NAME="csv-to-ec2-stack"

# AWSリージョンを自動取得。設定がなければ東京リージョンをデフォルトに
REGION=$(aws configure get region)
[ -z "$REGION" ] && REGION="ap-northeast-1"

# --- 関数定義 ---

# 使い方を表示
usage() {
    echo "使い方: $0 {deploy|upload|delete}"
    echo
    echo "コマンド:"
    echo "  deploy   : AWSリソース（VPC, S3, Lambda等）をデプロイします。"
    echo "  upload   : CSVファイルをS3にアップロードし、EC2インスタンス作成をトリガーします。"
    echo "  delete   : 作成したすべてのAWSリソースを削除します。"
    echo
}

# 必須コマンドとAWS認証情報の存在をチェック
check_requirements() {
    echo ">>> 前提条件を確認しています..."
    local has_error=0

    # AWS CLIのチェック
    if ! command -v aws &> /dev/null; then
        echo "エラー: AWS CLI ('aws') が見つかりません。インストールしてください。" >&2
        has_error=1
    elif ! aws sts get-caller-identity > /dev/null 2>&1; then
        echo "エラー: AWS認証情報が正しく設定されていません。'aws configure'を実行してください。" >&2
        has_error=1
    fi

    # AWS SAM CLIのチェック
    if ! command -v sam &> /dev/null; then
        echo "エラー: AWS SAM CLI ('sam') が見つかりません。インストールしてください。" >&2
        has_error=1
    fi

    if [ "$has_error" -ne 0 ]; then
        exit 1
    fi
    echo "✔ AWS CLI, SAM CLI, 認証情報は正常です。"
}

# SAMスタックのビルドとデプロイ
deploy_stack() {
    echo ">>> SAMアプリケーションをビルドしています..."
    sam build

    echo ">>> スタック '$STACK_NAME' をリージョン '$REGION' にデプロイしています..."
    sam deploy --stack-name "$STACK_NAME" --region "$REGION" --capabilities CAPABILITY_IAM --resolve-s3 --confirm-changeset

    echo ">>> デプロイ成功。S3バケット名を取得しています..."
    BUCKET_NAME=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" \
        --output text \
        --region "$REGION")

    if [ -z "$BUCKET_NAME" ]; then
        echo "エラー: S3バケット名を取得できませんでした。CloudFormationスタックの出力にS3BucketNameが存在するか確認してください。" >&2
        exit 1
    fi

    # 後続コマンドで使うため、バケット名をファイルに保存
    echo "S3_BUCKET_NAME=$BUCKET_NAME" > "$CONFIG_FILE"
    echo "REGION=$REGION" >> "$CONFIG_FILE"

    echo "✔ セットアップ完了。S3バケット '$BUCKET_NAME' の準備ができました。"
    echo "次に './manage.sh upload' を実行してEC2インスタンスを作成できます。"
}

# S3バケットへCSVファイルをアップロード
upload_csv() {
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "エラー: 設定ファイル '$CONFIG_FILE' が見つかりません。最初に './manage.sh deploy' を実行してください。" >&2
        exit 1
    fi
    source "$CONFIG_FILE"

    CSV_FILE="$1"
    # ファイル指定がない場合、カレントディレクトリのCSVファイルを自動検出
    if [ -z "$CSV_FILE" ]; then
        shopt -s nullglob
        CSV_FILES=(*.csv)
        shopt -u nullglob

        if [ ${#CSV_FILES[@]} -eq 1 ]; then
            CSV_FILE="${CSV_FILES[0]}"
            echo ">>> CSVファイルを自動検出しました: '$CSV_FILE'"
        elif [ ${#CSV_FILES[@]} -eq 0 ]; then
            echo "エラー: アップロードするCSVファイルが見つかりません。ファイルパスを指定してください。" >&2
            echo "使用例: ./manage.sh upload sample.csv" >&2
            exit 1
        else
            echo "エラー: 複数のCSVファイルが見つかりました。アップロードするファイルを1つ指定してください。" >&2
            exit 1
        fi
    fi

    if [ ! -f "$CSV_FILE" ]; then
        echo "エラー: CSVファイル '$CSV_FILE' が見つかりません。ファイルが存在するか、パスが正しいか確認してください。" >&2
        exit 1
    fi

    echo ">>> '$CSV_FILE' をバケット '$S3_BUCKET_NAME' にアップロードしています..."
    aws s3 cp "$CSV_FILE" "s3://$S3_BUCKET_NAME/"

    echo "✔ ファイルがアップロードされました。EC2インスタンスの作成が開始されます。"
}

# SAMスタックの削除
delete_stack() {
    echo ">>> SAMスタック '$STACK_NAME' の削除を開始します..."

    # バケットが空でないとスタックを削除できないため、中身を先に空にする
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
        if [ -n "$S3_BUCKET_NAME" ]; then
            if aws s3api head-bucket --bucket "$S3_BUCKET_NAME" &>/dev/null; then
                echo ">>> S3バケット '$S3_BUCKET_NAME' の中身を空にしています..."
                aws s3 rm "s3://$S3_BUCKET_NAME/" --recursive
            else
                echo ">>> S3バケット '$S3_BUCKET_NAME' が存在しないため、削除をスキップします。"
            fi
        fi
    fi

    # EC2インスタンスの削除
    INSTANCE_IDS=$(aws ec2 describe-instances \
        --filters "Name=tag:CreatedByStack,Values=$STACK_NAME" "Name=instance-state-name,Values=pending,running,stopping,stopped,shutting-down,terminated" \
        --query "Reservations[].Instances[].InstanceId" \
        --output text \
        --region "$REGION")

    if [ -n "$INSTANCE_IDS" ]; then
        echo ">>> EC2インスタンスを削除しています: $INSTANCE_IDS"
        aws ec2 terminate-instances --instance-ids $INSTANCE_IDS --region "$REGION" > /dev/null
        echo ">>> インスタンスの終了を待機しています..."
        aws ec2 wait instance-terminated --instance-ids $INSTANCE_IDS --region "$REGION"
        echo "✔ EC2インスタンスが削除されました。"
    else
        echo ">>> 削除対象のEC2インスタンスは見つかりませんでした。"
    fi

    echo ">>> SAMスタック '$STACK_NAME' をリージョン '$REGION' から削除します..."
    sam delete --stack-name "$STACK_NAME" --region "$REGION" --no-prompts

    # ローカルの設定ファイルを削除
    rm -f "$CONFIG_FILE"

    echo "✔ スタックの削除が完了しました。"
}

# --- スクリプトのエントリポイント ---

# 最初に前提条件を確認
check_requirements

# コマンドに応じて処理を振り分け
case "$1" in
    deploy)
        deploy_stack
        ;;
    upload)
        upload_csv "$2"
        ;;
    delete)
        delete_stack
        ;;
    ""|--help|-h)
        usage
        ;;
    *)
        echo "エラー: 不明なコマンド '$1'" >&2
        usage
        exit 1
        ;;
esac

exit 0
