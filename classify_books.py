#!/usr/bin/env python3
"""
翔泳社 Kindle 一覧の統合JSONを読み、タイトルからカテゴリ・タグを付与して保存する。
"""

import argparse
import json
import os
from pathlib import Path

# .env から GEMINI_API_KEY などを読み込む（--use-api 時用）
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

# カテゴリとキーワード（先にマッチした方を優先するため、具体的なものから並べる）
CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("資格試験・PMP", ["PMP", "PMBOK", "PM教科書", "プロジェクトマネジメント"]),
    ("資格試験・G検定", ["G検定", "ジェネラリスト"]),
    ("資格試験・AWS", ["AWS", "Amazon Web Services", "ソリューションアーキテクト"]),
    ("資格試験・Azure", ["Azure", "AI-900", "AI-102", "AZ-", "MCP教科書"]),
    ("資格試験・オラクル", ["オラクルマスター", "Oracle Master", "Silver", "Bronze", "Gold", "PL/SQL"]),
    ("資格試験・シスコ", ["CCNA", "CCNP", "シスコ", "Cisco"]),
    ("データベース", ["DB設計", "達人に学ぶDB", "データベース", "Oracle Database", "SQL"]),
    ("インフラ・ネットワーク", ["Kubernetes", "Docker", "Linux", "ネットワーク", "インフラ", "サーバー", "クラウド", "ログ"]),
    ("AI・機械学習", ["機械学習", "深層学習", "TensorFlow", "PyTorch"]),
    # プログラミング言語別（具体的なキーワードから。先にマッチした方が優先）
    ("Python", ["Python"]),
    ("Java", ["Java"]),
    ("Kotlin", ["Kotlin"]),
    ("Go", ["Go言語", "Golang", " Go "]),  # "Go" 単体は短いので「Go言語」等を優先
    ("Rust", ["Rust"]),
    ("C#", ["C#", "C Sharp", "Unity"]),
    ("C・C++", ["C言語", "C++"]),
    ("Ruby", ["Ruby"]),
    ("PHP", ["PHP"]),
    ("Swift", ["Swift"]),
    ("Scala", ["Scala"]),
    ("R", [" R ", "R言語", "Rで学ぶ", "Rによる"]),  # 単体 "R" は他と被るので文脈付き
    ("Web・フロントエンド", ["JavaScript", "TypeScript", "React", "Vue", "フロントエンド", "HTML", "CSS"]),
    ("Git・開発ツール", ["Git", "GitHub"]),
    ("開発手法・アジャイル", ["アジャイル", "スクラム", "SCRUM", "ドメイン駆動", "DDD", "リファクタリング", "テスト駆動", "TDD", "コードレビュー", "プロダクトマネジメント"]),
    ("設計・アーキテクチャ", ["アーキテクチャ", "設計パターン", "ドメイン設計"]),
    ("プログラミング・開発", ["プログラミング", "入門", "開発", "コード", "アプリ", "設計"]),
    ("デザイン", ["デザイン", "UI", "UX", "Figma", "Illustrator"]),
    ("投資・金融", ["株", "投資", "四季報", "資産", "マネー", "FX", "株式"]),
    ("ビジネス・マネジメント", ["ビジネス", "マネジメント", "サクセス", "説明の技術", "伝わる", "リーダー", "チーム", "組織"]),
    ("メンタル・自己啓発", ["メンタル", "自己啓発", "心理", "ストレス", "はたらく"]),
    ("資格試験・その他", ["資格", "検定", "試験", "公式テキスト", "合格", "教科書"]),
    ("その他", []),
]

DEFAULT_ENRICHED_NAME = "books_enriched.json"
DEFAULT_CATEGORIES_NAME = "categories.json"


def get_keyword_category_names() -> list[str]:
    """現在のキーワードルールで定義しているカテゴリ名のリスト（順序保持）。"""
    return [cat for cat, _ in CATEGORY_KEYWORDS]


def extract_categories_to_file(path: Path, category_names: list[str]) -> None:
    """カテゴリ名の一覧をJSON配列で保存する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(category_names, ensure_ascii=False, indent=2), encoding="utf-8")


def load_categories_from_file(path: Path) -> list[str] | None:
    """data/categories.json などからカテゴリ名の一覧を読み込む。"""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else None
    except (json.JSONDecodeError, OSError):
        return None


def extract_categories_with_api(books: list[dict], output_path: Path, api_key: str) -> bool:
    """全タイトルを元にAPIでカテゴリ候補を抽出し、output_path に保存する。"""
    try:
        from google import genai
    except ImportError:
        print("Run: pip install google-genai")
        return False
    titles = [b.get("title") or "" for b in books if b.get("title")]
    if not titles:
        return False
    # 最大で約500件までプロンプトに載せる（トークン制限を考慮）
    sample = titles[:500] if len(titles) > 500 else titles
    title_list = "\n".join(f"- {t}" for t in sample)
    model_name = os.environ.get("MODEL_NAME") or "gemini-2.0-flash"
    client = genai.Client(api_key=api_key)
    prompt = f"""以下は翔泳社の技術書・ビジネス書のKindle本タイトル一覧です。
これらを書店の棚のように分類するとき、読者が探しやすい「カテゴリ名」を考えてください。

【ルール】
- 日本語でカテゴリ名を付ける
- 15〜35個程度にまとめる
- 資格試験系・プログラミング言語・インフラ・ビジネス・デザインなど、内容が分かるようにする
- 重複や包含関係にならないようにする
- 返答はJSON配列のみ。説明や改行は入れず、例: ["カテゴリ1", "カテゴリ2"]

【タイトル一覧】
{title_list}

【上記を踏まえたカテゴリ名のJSON配列】"""
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        text = (response.text or "").strip()
        # コードブロックを外す
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        arr = json.loads(text)
        if not isinstance(arr, list) or not all(isinstance(x, str) for x in arr):
            print("API returned invalid format.")
            return False
        extract_categories_to_file(output_path, arr)
        print(f"Extracted {len(arr)} categories (from API) -> {output_path}")
        return True
    except Exception as e:
        print(f"API error: {e}")
        return False


def classify_by_keywords(title: str) -> tuple[str, list[str]]:
    """タイトルからカテゴリとタグ（キーワードの一部）を返す。"""
    title_lower = title
    for category, keywords in CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in title_lower:
                tags = [kw] if kw in title_lower else []
                return category, tags
    return "その他", []


def load_books(path: Path) -> list[dict]:
    """JSONファイルから書籍リストを読み込む。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def classify_books(books: list[dict], skip_existing: bool = True) -> list[dict]:
    """各書籍に category と tags を付与する。skip_existing が True のときは既に category があるものはスキップ。"""
    result = []
    for b in books:
        book = dict(b)
        if skip_existing and book.get("category"):
            result.append(book)
            continue
        title = book.get("title") or ""
        category, tags = classify_by_keywords(title)
        book["category"] = category
        book["tags"] = book.get("tags") or tags
        result.append(book)
    return result


def main():
    parser = argparse.ArgumentParser(description="統合JSONを分類し、カテゴリ・タグ付きで保存する")
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=Path("data/all_books.json"),
        help="入力JSON（統合済み書籍リスト）",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        metavar="FILE",
        help=f"出力JSON（default: 入力と同じディレクトリの {DEFAULT_ENRICHED_NAME}）",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="既に category が付いている書籍も再分類する",
    )
    parser.add_argument(
        "--extract-categories",
        action="store_true",
        help="全カテゴリ一覧を data/categories.json に出力する（キーワード定義から抽出。APIで抽出する場合は --use-api を併用）",
    )
    parser.add_argument(
        "--use-api",
        action="store_true",
        help="--extract-categories 時: タイトルをAPIに送り、カテゴリ候補を抽出する。要 GOOGLE_API_KEY",
    )
    parser.add_argument(
        "--categories-file",
        type=Path,
        metavar="FILE",
        default=Path("data/categories.json"),
        help="extract 時の出力先 / 分類時に参照するカテゴリ一覧 (default: data/categories.json)",
    )
    args = parser.parse_args()

    # カテゴリ抽出のみ（分類は行わない）
    if args.extract_categories:
        if args.use_api:
            if not args.input.exists():
                print(f"Error: {args.input} not found.")
                return 1
            books = load_books(args.input)
            if not books:
                print("No books in input.")
                return 1
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                print("Set GEMINI_API_KEY in .env (or GOOGLE_API_KEY) to use --use-api.")
                return 1
            if not extract_categories_with_api(books, args.categories_file, api_key):
                return 1
        else:
            names = get_keyword_category_names()
            extract_categories_to_file(args.categories_file, names)
            print(f"Extracted {len(names)} categories (from keyword rules) -> {args.categories_file}")
        return 0

    if not args.input.exists():
        print(f"Error: {args.input} not found.")
        return 1

    books = load_books(args.input)
    if not books:
        print("No books in input.")
        return 1

    enriched = classify_books(books, skip_existing=not args.no_skip)
    out_path = args.output or (args.input.parent / DEFAULT_ENRICHED_NAME)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(enriched, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Classified {len(enriched)} books -> {out_path}")

    # カテゴリ別件数
    from collections import Counter
    counts = Counter(b["category"] for b in enriched)
    for cat, n in counts.most_common():
        print(f"  {cat}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
