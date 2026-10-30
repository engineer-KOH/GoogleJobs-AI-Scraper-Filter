# 🚀 GoogleJobs-AI-Scraper-Filter

## 📌 概要（Overview）
このシステムは、求人検索プラットフォーム（Google Jobs等）から取得した求人データを自動でスクレイピング・収集し、AIモデルを活用して希望条件やスキルセットに合致する案件を高精度にフィルタリング・選別するためのPythonツールです。  
手動での求人検索や条件絞り込みにかかる膨大な工数を削減し、効率的な情報収集を実現します。

## 🎯 主な目的（Objective）
- **情報収集の自動化**: 求人サイトからのデータ自動スクレイピングと蓄積
- **AIによる高精度フィルタリング**: 単なるキーワード一致にとどまらない、AIによる柔軟な条件適合性の評価・選別
- **キャリア・市場調査の効率化**: 自身のスキルや希望条件にマッチする求人トレンドの素早い把握

## 🛠️ 使用技術（Tech Stack）
- **言語**: Python
- **主要ライブラリ**: `pandas`, `requests`, `BeautifulSoup` / スクレイピング・API関連ライブラリ
- **AI・連携**: LLM / AIモデルを活用したテキスト評価・フィルタリング機構

## ⚙️ システム構成・処理フロー（Workflow）
- **入力 (Inputs)**: 検索キーワード、地域、希望条件などの設定データの読み込み
- **処理 (Process)**: Webからの求人データ自動スクレイピング、データの正規化、およびAIモデルによるスキル・条件マッチング評価
- **出力 (Outputs)**: 条件に最適化された求人リストおよび分析結果レポートの出力

## 🚀 使い方（Quick Start）
- **💻 1. 開発者・セットアップ手順**:
- **1.リポジトリのクローン**: 「git clone [https://github.com/mochapaparocku-crypto/GoogleJobs-AI-Scraper-Filter.git](https://github.com/mochapaparocku-crypto/GoogleJobs-AI-Scraper-Filter.git)」
- **2.依存ライブラリのインストール**: 「pip install -r requirements.txt」
- **👤 2. スクリプトの実行フロー**:
- **1.**: 必要に応じて inputs/ フォルダ内の検索条件パラメータを調整します。
- **2.**: スクレイピングおよびフィルタリング処理を実行します。「python job_search.py」
- **3.**: 処理完了後、outputs/ フォルダに抽出・フィルタリングされた求人結果が出力されます。

## 📁 フォルダ構成（Repository Structure）
```text
GoogleJobs-AI-Scraper-Filter/
├── inputs/                    # 検索条件や入力設定ファイル群
├── outputs/                   # フィルタリング・抽出された求人分析結果の出力先
├── logs/                      # 実行ログの保存先
├── job_search.py              # 求人収集・AIフィルタリング実行メインスクリプト
└── .gitignore                 # 機密情報・ログ・成果物（*.key, .env等）の除外設定
