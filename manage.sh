#!/bin/bash

# csv-to-ec2 SAMアプリケーションのデプロイと管理を行うスクリプト

# エラー発生時にスクリプトを停止
set -e

# --- 設定 ---
# SAMデプロイのアウトプット（S3バケット名など）を保存するファイル
CONFIG_FILE=".sam_outputs"

# CloudFormationのスタック名（変更可能）
STACK_NAME="csv-to-ec2-stack"

# AWSリージョンを自動取得。設定がなければ東京リージョンをデフォルトに
REGION=$(aws configure get region)
[ -z "$REGION" ] && REGION="ap-northeast-1"

# --- ヘルパー関数 ---
# 使い方を表示
usage() {
    echo "使い方: $0 {deploy|upload|delete}"
    echo
    echo "コマンド:"
    echo "  deploy   : AWS SAMスタックをビルド・デプロイします。ネットワークリソース、S3バケット、Lambdaを作成します。"
    echo "  upload   : S3バケットにCSVファイルをアップロードし、EC2インスタンス作成をトリガーします。"
    echo "           : 引数なしの場合、カレントディレクトリに存在する単一の.csvファイルを自動で検出します。"
    echo "  delete   : 作成されたすべてのAWSリソース（SAMスタック）を削除します。"
    echo
}

# --- メイン関数 ---
# SAMスタックのビルドとデプロイ
deploy_stack() {
    echo ">>> SAMアプリケーションをビルドしています..."
    sam build

    echo ">>> スタック '$STACK_NAME' をリージョン '$REGION' にデプロイしています..."
    # --guided オプションは初回デプロイ時に役立ちます。2回目以降は samconfig.toml が使用されます。
    sam deploy --stack-name "$STACK_NAME" --region "$REGION" --capabilities CAPABILITY_IAM --resolve-s3 --confirm-changeset

    echo ">>> デプロイ成功。S3バケット名を取得しています..."

    # CloudFormationスタックのアウトプットからS3バケット名を取得
    BUCKET_NAME=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" \
        --output text \
        --region "$REGION")

    if [ -z "$BUCKET_NAME" ]; then
        echo "エラー: S3バケット名を取得できませんでした。"
        echo "AWSマネジメントコンソールでスタックの状態を確認してください。"
        exit 1
    fi

    # 後続の 'upload' コマンドで使うため、バケット名をファイルに保存
    echo "S3_BUCKET_NAME=$BUCKET_NAME" > "$CONFIG_FILE"

    echo "✔ セットアップ完了。"
    echo "  S3バケット '$BUCKET_NAME' の準備ができました。"
    echo "  './manage.sh upload' コマンドでEC2インスタンスを作成できます。"
}

# S3バケットへCSVファイルをアップロード
upload_csv() {
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "エラー: 設定ファイル '$CONFIG_FILE' が見つかりません。"
        echo "最初に './manage.sh deploy' を実行してください。"
        exit 1
    fi

    # 設定ファイルからバケット名を読み込む
    source "$CONFIG_FILE"

    if [ -z "$S3_BUCKET_NAME" ]; then
        echo "エラー: '$CONFIG_FILE' 内に S3_BUCKET_NAME が見つかりません。"
        exit 1
    fi

    CSV_FILE="$1" # 引数で渡されたファイルパス
    if [ -z "$CSV_FILE" ]; then
        # 引数がない場合、カレントディレクトリから.csvファイルを自動検出
        shopt -s nullglob
        CSV_FILES=(*.csv)
        shopt -u nullglob

        if [ ${#CSV_FILES[@]} -eq 1 ]; then
            CSV_FILE="${CSV_FILES[0]}"
            echo ">>> CSVファイルを自動検出しました: '$CSV_FILE'"
        elif [ ${#CSV_FILES[@]} -eq 0 ]; then
            echo "エラー: カレントディレクトリにCSVファイルが見つかりません。"
            echo "CSVファイルを配置するか、ファイルパスを指定してください:"
            echo "  使用例: ./manage.sh upload sample.csv"
            exit 1
        else
            echo "エラー: 複数のCSVファイルが見つかりました。アップロードするファイルを指定してください:"
            printf " - %s\n" "${CSV_FILES[@]}"
            echo "  使用例: ./manage.sh upload ${CSV_FILES[0]}"
            exit 1
        fi
    fi

    if [ ! -f "$CSV_FILE" ]; then
        echo "エラー: CSVファイル '$CSV_FILE' が見つかりません。"
        exit 1
    fi

    echo ">>> '$CSV_FILE' をバケット '$S3_BUCKET_NAME' にアップロードしています..."
    aws s3 cp "$CSV_FILE" "s3://$S3_BUCKET_NAME/"

    echo "✔ ファイルがアップロードされました。EC2インスタンスの作成がトリガーされます。"
}

# SAMスタックの削除
delete_stack() {
    echo ">>> SAMスタック '$STACK_NAME' の削除準備をしています..."

    # 設定ファイルからバケット名を取得して、バケット内を空にする
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
        if [ -n "$S3_BUCKET_NAME" ]; then
            echo ">>> S3バケット '$S3_BUCKET_NAME' の中身を空にしています..."
            # バケットが存在するか確認してから削除コマンドを実行
            if aws s3api head-bucket --bucket "$S3_BUCKET_NAME" 2>/dev/null; then
                aws s3 rm "s3://$S3_BUCKET_NAME/" --recursive
            else
                echo "-> バケット '$S3_BUCKET_NAME' は既に存在しないため、スキップします。"
            fi
        fi
    else
        echo "-> 設定ファイルが見つかりません。S3バケットのクリーンアップはスキップします。"
    fi

    echo ">>> SAMスタック '$STACK_NAME' をリージョン '$REGION' から削除します..."
    echo "!!! 注意: この操作により、本スクリプトで作成されたすべてのAWSリソースが削除されます。!!!"

    sam delete --stack-name "$STACK_NAME" --region "$REGION" --no-prompts

    # ローカルの設定ファイルをクリーンアップ
    if [ -f "$CONFIG_FILE" ]; then
        rm "$CONFIG_FILE"
    fi

    echo "✔ スタックの削除が完了しました。"
}

# --- スクリプトのエントリポイント ---
# 必要なコマンドの存在チェック
if ! command -v sam &> /dev/null || ! command -v aws &> /dev/null; then
    echo "エラー: 'sam' および 'aws' CLIが必要です。"
    echo "これらをインストールし、AWS認証情報を設定してください。"
    exit 1
fi

# メインのコマンド振り分け
case "$1" in
    deploy)
        deploy_stack
        ;;
    upload)
        # 2番目の引数（ファイル名）をupload関数に渡す
        upload_csv "$2"
        ;;
    delete)
        delete_stack
        ;;
    ""|--help|-h) # 引数なし、またはヘルプオプションの場合
        usage
        exit 0
        ;;
    *)
        echo "エラー: 不明なコマンド '$1'"
        usage
        exit 1
        ;;
esac

exit 0
