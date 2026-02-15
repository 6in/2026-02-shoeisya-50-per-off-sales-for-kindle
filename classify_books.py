#!/usr/bin/env python3
"""
翔泳社 Kindle 一覧の統合JSONを読み、タイトルからカテゴリ・タグを付与して保存する。
"""

import argparse
import json
from pathlib import Path

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
    # プログラミング・開発を細分化（上のいずれにも当てはまらないもの用）
    ("Python", ["Python"]),
    ("Java・Kotlin", ["Java", "Kotlin"]),
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
    args = parser.parse_args()

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
