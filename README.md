# 翔泳社 Kindle 50%オフ セール一覧

Amazon.co.jp の翔泳社 Kindle 50%オフセールページをスクレイピングし、全カタログを1つのHTMLで表示するツールです。

## 必要な環境

- Python 3.10+
- requests, beautifulsoup4

## セットアップ

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 使い方

**テスト（1ページだけ取得）**

```bash
python scrape_shoeisya_kindle.py --test -o shoeisya_kindle_list.html
```

**全67ページを取得（約3分程度）**

```bash
python scrape_shoeisya_kindle.py -o shoeisya_kindle_list.html
```

**キャッシュと再開**

- 各ページの取得結果は **データのみ** が `data/` 配下に `page_001.json` … `page_067.json` で保存されます。
- 次回実行時、すでに存在するページのJSONは **スキップ** し、未取得のページだけ取得します。途中で止めた場合も再実行で続きから取得できます。
- キャッシュを使わず最初から取得し直す場合は `--no-cache` を付けてください。

**統合JSON**

- 取得完了後、全ページ分のデータを **1つのJSON** にまとめて `data/all_books.json` に保存します。
- 取得をスキップし、既存のページ別JSONだけを統合する場合は `--merge-only` を指定します。

```bash
python scrape_shoeisya_kindle.py --merge-only
```

**オプション**

- `--pages N` … 取得する最大ページ数（既定: 67）
- `--delay 秒` … ページ間の待機秒数（既定: 2.5）
- `-o ファイル` … 出力HTMLのパス
- `-m FILE`, `--merged-json FILE` … 統合JSONの保存先（既定: cache-dir/all_books.json）
- `--merge-only` … 取得せず、既存の page_*.json だけを読み込んで1ファイルに統合
- `-c DIR`, `--cache-dir DIR` … ページ別データの保存先（既定: `data`）
- `--no-cache` … キャッシュを無視して全ページ再取得
- `--debug-html FILE` … 1ページ目のHTMLを保存（デバッグ用）

## 出力

`shoeisya_kindle_list.html` をブラウザで開くと、表紙・タイトル・著者・価格・評価・Amazonリンクが一覧で表示されます。

## カテゴリ別表示

1. **分類** … 統合JSONにタイトルからカテゴリを付与する。

```bash
python classify_books.py data/all_books.json -o data/books_enriched.json
```

2. **カテゴリ別HTMLの生成** … 分類済みJSONから、カテゴリごとのセクションでHTMLを出力する。

```bash
python scrape_shoeisya_kindle.py --enriched data/books_enriched.json -o shoeisya_kindle_list.html
```

- `classify_books.py` のオプション: `--no-skip` で既存の category も再分類。入力省略時は `data/all_books.json` を使用。
- カテゴリはキーワードルールで自動付与（資格試験・データベース・インフラ・AI・プログラミング・デザイン・投資・ビジネス・メンタル・その他 など）。

## 注意

- 取得頻度を抑えるため、ページ間に2.5秒の待機を入れています。
- Amazonの利用規約・robots.txtを確認のうえ、個人利用の範囲でご利用ください。
