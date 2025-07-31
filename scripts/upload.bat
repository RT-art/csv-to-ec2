@echo off
rem UTF-8表示に対応
chcp 65001 > nul

rem =================================================================
rem CSVをS3にアップロードし、EC2インスタンスを作成します。
rem =================================================================

rem --- 設定項目 ---
set CSV_FILE=sample.csv
set S3_BUCKET=s3://rt-ec2-to-csv-bucket

echo.
echo === 事前チェックを開始します ===

rem 1. CSVファイルの存在確認
if not exist "%CSV_FILE%" (
    echo [NG] CSVファイルが見つかりません。
    echo     -> "%CSV_FILE%" がこのバッチファイルと同じフォルダにあるか確認してください。
    goto :end
)
echo [OK] CSVファイルが見つかりました。 (%CSV_FILE%)

rem 2. AWS CLIのインストール確認
aws --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [NG] AWS CLIが見つかりません。
    echo     -> AWS CLIがインストールされているか確認してください。
    goto :end
)
echo [OK] AWS CLIはインストールされています。

rem 3. AWS認証情報・接続確認
echo [..] AWSへの接続と認証情報を確認中...
aws sts get-caller-identity > nul 2>&1
if %errorlevel% neq 0 (
    echo [NG] AWSの認証情報が無効か、接続に問題があります。
    echo     -> ターミナルで `aws configure` の設定が正しいか確認してください。
    goto :end
)
echo [OK] AWSの認証情報は有効です。

echo === 事前チェック完了 ===
echo.

rem --- 実行処理 ---
echo %CSV_FILE% を %S3_BUCKET% にアップロードします...
echo.

rem AWS CLIを実行し、エラー出力を一時ファイルに保存
aws s3 cp "%CSV_FILE%" "%S3_BUCKET%/" 2> error.log

rem --- 結果判定 ---
if %errorlevel% equ 0 (
    echo [成功] アップロードに成功しました！
    echo       AWSコンソールでEC2インスタンスの作成状況を確認してください。
) else (
    echo [エラー] アップロードに失敗しました。
    echo.
    echo ---エラー詳細---
    rem エラーログの内容を表示
    type error.log
    echo ---ここまで---
)

rem --- 後処理 ---
del error.log > nul 2>&1

:end
echo.
pause