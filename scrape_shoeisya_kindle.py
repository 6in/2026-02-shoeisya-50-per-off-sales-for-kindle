#!/usr/bin/env python3
"""
翔泳社 Kindle 50%オフセール一覧をスクレイピングし、1つのHTMLに出力する。
各ページのデータはJSONで保存し、取得済みページはスキップ。最後に全データをまとめてHTML出力。
"""

import json
import time
import argparse
from pathlib import Path
from urllib.parse import urljoin, urlencode, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

BASE_URL = (
    "https://www.amazon.co.jp/s"
    "?i=digital-text"
    "&srs=214982203051"
    "&rh=n%3A214982203051"
    "&s=popularity-rank"
    "&fs=true"
    "&ref=lp_214982203051_sar"
)
AMAZON_BASE = "https://www.amazon.co.jp"
DEFAULT_DELAY = 2.5
DEFAULT_PAGES = 67
DEFAULT_CACHE_DIR = "data"
MERGED_JSON_NAME = "all_books.json"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def build_page_url(base_url: str, page: int) -> str:
    """ページ番号付きURLを組み立てる。page=1 のときはクエリに含めない場合もあるが、含めても動作する。"""
    parsed = urlparse(base_url)
    qs = parse_qs(parsed.query)
    qs["page"] = [str(page)]
    new_query = urlencode(qs, doseq=True)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"


def extract_text(el, default: str = "") -> str:
    if el is None:
        return default
    t = el.get_text(strip=True)
    return t if t else default


def parse_search_page(html: str) -> list[dict]:
    """1ページ分のHTMLから商品リストを抽出する。"""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # 商品ブロック: data-component-type="s-search-result" かつ data-asin が空でないもの
    for div in soup.find_all("div", attrs={"data-component-type": "s-search-result"}):
        asin = div.get("data-asin") or ""
        if not asin or asin.strip() == "":
            continue

        # タイトル & リンク（構造: a > h2 > span。data-cy=title-recipe の a が商品ページへのリンク）
        title_link_el = div.select_one("[data-cy=title-recipe] a[href*='/dp/']")
        if not title_link_el:
            title_link_el = div.select_one("a.s-link-style.a-text-normal[href*='/dp/']")
        title = ""
        link = ""
        if title_link_el:
            link = urljoin(AMAZON_BASE, title_link_el.get("href") or "")
            title_span = title_link_el.select_one("h2 span")
            title = extract_text(title_span)
        if not title:
            title = extract_text(div.select_one("h2.a-size-medium span"))

        # 画像
        img_el = div.select_one("img.s-image")
        image_url = (img_el.get("src") or "") if img_el else ""

        # 価格（現価格）
        price_el = div.select_one(".a-price .a-offscreen")
        price = extract_text(price_el)

        # 過去価格 / 定価（リスト価格）
        list_price_el = div.select_one(".a-price[data-a-strike] .a-offscreen")
        if not list_price_el:
            list_price_el = div.select_one(".a-text-price .a-offscreen")
        list_price = extract_text(list_price_el)

        # 著者（2行目によくある）
        author_el = div.select_one(".a-row.a-size-base.a-color-secondary")
        author = extract_text(author_el)

        # 評価
        rating_el = div.select_one(".a-icon-alt")
        rating = extract_text(rating_el)

        results.append({
            "asin": asin,
            "title": title,
            "author": author,
            "link": link,
            "image_url": image_url,
            "price": price,
            "list_price": list_price,
            "rating": rating,
        })

    return results


def fetch_page(session: requests.Session, url: str) -> str | None:
    """1ページ取得。失敗時は None。"""
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        print(f"  Error: {e}")
        return None


def cache_path(cache_dir: Path, page: int) -> Path:
    """ページ番号に対応するキャッシュファイルパスを返す。"""
    return cache_dir / f"page_{page:03d}.json"


def load_page_cache(cache_path: Path) -> list[dict] | None:
    """キャッシュファイルがあれば書籍リストを読み込む。なければ None。"""
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else None
    except (json.JSONDecodeError, OSError):
        return None


def save_page_cache(cache_path: Path, books: list[dict]) -> None:
    """1ページ分の書籍データをJSONで保存する。"""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(books, ensure_ascii=False, indent=0), encoding="utf-8")


def load_all_from_cache(cache_dir: Path, max_pages: int = 67) -> list[dict]:
    """キャッシュディレクトリ内の page_001.json ～ page_XXX.json を読み、1つのリストに統合する。"""
    all_books = []
    for page in range(1, max_pages + 1):
        cpath = cache_path(cache_dir, page)
        cached = load_page_cache(cpath)
        if cached is None:
            break
        all_books.extend(cached)
    return all_books


def save_merged_json(books: list[dict], path: Path) -> None:
    """全書籍データを1つのJSONファイルに保存する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(books, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Merged {len(books)} books -> {path}")


def _load_category_order() -> list[str]:
    """data/categories.json があればその順序を返す。なければ既定の順序。"""
    default = [
        "資格試験・PMP", "資格試験・G検定", "資格試験・AWS", "資格試験・Azure",
        "資格試験・オラクル", "資格試験・シスコ", "資格試験・その他",
        "データベース", "インフラ・ネットワーク", "AI・機械学習",
        "Python", "Java・Kotlin", "Web・フロントエンド", "Git・開発ツール",
        "開発手法・アジャイル", "設計・アーキテクチャ", "プログラミング・開発",
        "デザイン", "投資・金融", "ビジネス・マネジメント", "メンタル・自己啓発", "その他",
    ]
    path = Path("data/categories.json")
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list) and data and all(isinstance(x, str) for x in data):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return default


def _book_to_card(b: dict) -> str:
    """1冊分のカードHTMLを返す。"""
    title_esc = b["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    author_esc = b["author"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    link = b["link"] or "#"
    img = b["image_url"]
    price = b["price"]
    list_price = b["list_price"]
    rating = b["rating"]
    list_price_line = f'<span class="list-price">{list_price}</span>' if list_price else ""
    return f"""
            <li class="card">
                <a href="{link}" target="_blank" rel="noopener" class="card-link">
                    <div class="card-img-wrap">
                        <img src="{img}" alt="" loading="lazy" />
                    </div>
                    <div class="card-body">
                        <h3 class="card-title">{title_esc}</h3>
                        <p class="card-author">{author_esc}</p>
                        <p class="card-meta">
                            <span class="price">{price}</span>
                            {list_price_line}
                            <span class="rating">{rating}</span>
                        </p>
                    </div>
                </a>
            </li>
            """


def generate_html(books: list[dict], output_path: Path) -> None:
    """取得した書籍リストを1つのHTMLファイルに出力する。category があればカテゴリ別セクションで表示。"""
    from collections import defaultdict

    has_category = any(b.get("category") for b in books)
    if not has_category:
        rows = [_book_to_card(b) for b in books]
        cards_html = "\n".join(rows)
        body_content = f"""
    <div class="header">
        <h1>翔泳社 Kindle 50%オフ セール一覧</h1>
        <p class="count">合計 {len(books)} 冊</p>
    </div>
    <ul class="catalog">
        {cards_html}
    </ul>
"""
    else:
        # カテゴリ別にグループ化。data/categories.json があればその順序を使う
        category_order = _load_category_order()
        by_cat = defaultdict(list)
        for b in books:
            by_cat[b.get("category") or "その他"].append(b)
        # 順序リストにないカテゴリは末尾に追加
        for cat in by_cat:
            if cat not in category_order:
                category_order.append(cat)
        sections = []
        sidebar_links = []
        for idx, cat in enumerate(category_order):
            items = by_cat.get(cat, [])
            if not items:
                continue
            section_id = f"cat-{idx}"
            sidebar_links.append(f'        <a href="#{section_id}" class="sidebar-link">{cat}（{len(items)}冊）</a>')
            cards = "\n".join(_book_to_card(b) for b in items)
            sections.append(f"""
    <section class="category-section" id="{section_id}">
        <h2 class="category-title">{cat}（{len(items)}冊）</h2>
        <ul class="catalog">
            {cards}
        </ul>
    </section>
""")
        sidebar_html = "\n".join(sidebar_links)
        body_content = f"""
    <aside class="sidebar">
        <div class="view-toggle">
            <span class="view-toggle-label">表示</span>
            <div class="view-toggle-btns">
                <button type="button" id="view-list-btn" aria-pressed="false">リスト表示</button>
                <button type="button" id="view-grid-btn" class="active" aria-pressed="true">グリッド表示</button>
            </div>
        </div>
        <nav class="sidebar-nav">
            <div class="sidebar-title">カテゴリ</div>
{sidebar_html}
        </nav>
    </aside>
    <main class="main-content">
    <div class="main-header-fixed">
        <div class="header">
            <p class="count" id="count-msg" data-total="{len(books)}">合計 {len(books)} 冊</p>
        </div>
        <div class="search-bar">
            <input type="search" id="search-input" placeholder="タイトル・著者で検索..." autocomplete="off" />
        </div>
    </div>
""" + "\n".join(sections) + """
    </main>
    <script>
    (function () {
        var STORAGE_KEY = 'kindle-list-view';
        var listBtn = document.getElementById('view-list-btn');
        var gridBtn = document.getElementById('view-grid-btn');
        function setView(mode) {
            if (mode === 'list') {
                document.body.classList.add('view-list');
                listBtn.classList.add('active');
                listBtn.setAttribute('aria-pressed', 'true');
                gridBtn.classList.remove('active');
                gridBtn.setAttribute('aria-pressed', 'false');
            } else {
                document.body.classList.remove('view-list');
                gridBtn.classList.add('active');
                gridBtn.setAttribute('aria-pressed', 'true');
                listBtn.classList.remove('active');
                listBtn.setAttribute('aria-pressed', 'false');
            }
            try { localStorage.setItem(STORAGE_KEY, mode); } catch (e) {}
        }
        listBtn.addEventListener('click', function () { setView('list'); });
        gridBtn.addEventListener('click', function () { setView('grid'); });
        try { var saved = localStorage.getItem(STORAGE_KEY); if (saved === 'list') setView('list'); } catch (e) {}
        var searchInput = document.getElementById('search-input');
        var countMsg = document.getElementById('count-msg');
        var total = parseInt(countMsg.getAttribute('data-total') || '0', 10);
        var allCards = document.querySelectorAll('.card');
        var allSections = document.querySelectorAll('.category-section');
        function runSearch() {
            var q = (searchInput.value || '').trim().toLowerCase();
            var visibleCount = 0;
            allCards.forEach(function (card) {
                var titleEl = card.querySelector('.card-title');
                var authorEl = card.querySelector('.card-author');
                var text = ((titleEl && titleEl.textContent) || '') + ' ' + ((authorEl && authorEl.textContent) || '');
                var match = !q || text.toLowerCase().indexOf(q) !== -1;
                if (match) { card.classList.remove('search-no-match'); visibleCount++; }
                else { card.classList.add('search-no-match'); }
            });
            allSections.forEach(function (section) {
                var sectionCards = section.querySelectorAll('.card');
                var hasVisible = Array.prototype.some.call(sectionCards, function (c) { return !c.classList.contains('search-no-match'); });
                section.classList.toggle('search-no-visible', !hasVisible);
            });
            countMsg.textContent = q ? ('表示 ' + visibleCount + ' 冊（合計 ' + total + ' 冊）') : ('合計 ' + total + ' 冊');
        }
        if (searchInput) { searchInput.addEventListener('input', runSearch); searchInput.addEventListener('search', runSearch); }
    })();
    </script>
</body>
</html>
"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>翔泳社 Kindle 50%オフ セール一覧</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: "Helvetica Neue", Arial, "Hiragino Kaku Gothic ProN", sans-serif; margin: 0; padding: 0; background: #f5f5f5; display: flex; min-height: 100vh; }}
        .main-header-fixed {{ position: sticky; top: 0; z-index: 10; background: #f5f5f5; margin: -1rem -1rem 0 -1rem; padding: 1rem 1rem 0.5rem 1rem; }}
        .header {{ max-width: 1200px; margin: 0 auto 0.5rem; }}
        .count {{ color: #666; font-size: 0.95rem; margin: 0; }}
        .sidebar {{ flex-shrink: 0; width: 220px; background: #fff; box-shadow: 1px 0 4px rgba(0,0,0,0.08); padding: 1rem 0; position: sticky; top: 0; max-height: 100vh; overflow-y: auto; }}
        .sidebar-nav {{ display: flex; flex-direction: column; gap: 0.25rem; }}
        .sidebar-title {{ font-weight: bold; font-size: 0.9rem; color: #333; padding: 0 1rem 0.5rem; border-bottom: 1px solid #eee; margin-bottom: 0.5rem; }}
        .sidebar-link {{ display: block; padding: 0.35rem 1rem; font-size: 0.8rem; color: #0066c0; text-decoration: none; border-left: 3px solid transparent; }}
        .sidebar-link:hover {{ background: #f0f7ff; border-left-color: #0066c0; }}
        .view-toggle {{ padding: 0 1rem 0.75rem; margin-bottom: 0.5rem; border-bottom: 1px solid #eee; }}
        .view-toggle-label {{ font-size: 0.75rem; color: #666; margin-bottom: 0.35rem; display: block; }}
        .view-toggle-btns {{ display: flex; gap: 0.25rem; }}
        .view-toggle-btns button {{ flex: 1; padding: 0.4rem 0.5rem; font-size: 0.75rem; border: 1px solid #ccc; background: #fff; color: #333; border-radius: 4px; cursor: pointer; }}
        .view-toggle-btns button:hover {{ background: #f5f5f5; border-color: #999; }}
        .view-toggle-btns button.active {{ background: #0066c0; color: #fff; border-color: #0066c0; }}
        .main-content {{ flex: 1; padding: 1rem; min-width: 0; }}
        .main-content .header {{ padding-left: 0; }}
        .search-bar {{ max-width: 1200px; margin: 0 auto 0; }}
        .search-bar input {{ width: 100%; max-width: 400px; padding: 0.5rem 0.75rem; font-size: 1rem; border: 1px solid #ccc; border-radius: 6px; }}
        .search-bar input:focus {{ outline: none; border-color: #0066c0; box-shadow: 0 0 0 2px rgba(0,102,192,0.2); }}
        .card.search-no-match {{ display: none !important; }}
        .category-section.search-no-visible {{ display: none; }}
        .category-section {{ max-width: 1200px; margin: 0 auto 2rem; scroll-margin-top: 1rem; }}
        .category-title {{ font-size: 1.1rem; color: #333; margin: 0 0 0.75rem; padding-bottom: 0.25rem; border-bottom: 2px solid #0066c0; }}
        ul.catalog {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }}
        body.view-list ul.catalog {{ display: flex; flex-direction: column; gap: 0.5rem; grid-template-columns: none; }}
        body.view-list .card {{ display: flex; max-width: 100%; }}
        body.view-list .card-link {{ display: flex; flex: 1; flex-direction: row; align-items: stretch; min-height: 0; }}
        body.view-list .card-img-wrap {{ width: 72px; min-width: 72px; aspect-ratio: auto; height: auto; align-self: stretch; }}
        body.view-list .card-img-wrap img {{ width: 72px; height: 96px; object-fit: cover; }}
        body.view-list .card-body {{ flex: 1; padding: 0.5rem 0.75rem; min-width: 0; display: flex; flex-direction: column; justify-content: center; }}
        body.view-list .card-title {{ -webkit-line-clamp: 2; }}
        .card {{ margin: 0; padding: 0; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
        .card-link {{ text-decoration: none; color: inherit; display: block; height: 100%; }}
        .card-img-wrap {{ aspect-ratio: 3/4; background: #eee; overflow: hidden; }}
        .card-img-wrap img {{ width: 100%; height: 100%; object-fit: cover; }}
        .card-body {{ padding: 0.75rem; }}
        .card-title {{ margin: 0 0 0.25rem; font-size: 0.9rem; line-height: 1.35; color: #0066c0; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }}
        .card-author {{ margin: 0; font-size: 0.8rem; color: #666; }}
        .card-meta {{ margin: 0.5rem 0 0; font-size: 0.85rem; }}
        .price {{ font-weight: bold; color: #b12704; }}
        .list-price {{ color: #888; text-decoration: line-through; margin-left: 0.5rem; }}
        .rating {{ display: block; margin-top: 0.25rem; color: #666; }}
        @media (max-width: 768px) {{ .sidebar {{ width: 100%; max-height: none; position: relative; }} body {{ flex-direction: column; }} .sidebar-nav {{ flex-direction: row; flex-wrap: wrap; }} .sidebar-link {{ flex: 1 1 auto; min-width: 140px; }} }}
    </style>
</head>
<body>
{body_content}
"""
    output_path.write_text(html, encoding="utf-8")
    print(f"Wrote: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="翔泳社 Kindle セール一覧をスクレイピングしてHTML出力")
    parser.add_argument(
        "--pages",
        type=int,
        default=DEFAULT_PAGES,
        help=f"取得する最大ページ数 (default: {DEFAULT_PAGES})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"ページ間の待機秒数 (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("shoeisya_kindle_list.html"),
        help="出力HTMLファイルパス",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="テスト用: 1ページだけ取得",
    )
    parser.add_argument(
        "--debug-html",
        type=Path,
        metavar="FILE",
        help="1ページ目のHTMLを保存（デバッグ用）",
    )
    parser.add_argument(
        "-c", "--cache-dir",
        type=Path,
        default=Path(DEFAULT_CACHE_DIR),
        help=f"ページ別データの保存先ディレクトリ (default: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="キャッシュを使わず毎回取得する",
    )
    parser.add_argument(
        "-m", "--merged-json",
        type=Path,
        metavar="FILE",
        help="全ページ分のJSONを1ファイルに統合して保存するパス (default: cache-dir/all_books.json)",
    )
    parser.add_argument(
        "--merge-only",
        action="store_true",
        help="取得は行わず、既存のページ別JSONを読み込んで1つに統合し、--merged-json に保存する",
    )
    parser.add_argument(
        "--enriched",
        type=Path,
        metavar="FILE",
        help="分類済みJSONを読み、カテゴリ別HTMLのみ出力する（取得・統合は行わない）",
    )
    args = parser.parse_args()

    # 分類済みJSONからHTMLのみ生成
    if args.enriched:
        if not args.enriched.exists():
            print(f"Error: {args.enriched} not found. Run classify_books.py first.")
            return
        books = json.loads(args.enriched.read_text(encoding="utf-8"))
        if not isinstance(books, list) or not books:
            print("Error: enriched file has no book list.")
            return
        generate_html(books, args.output)
        print(f"Done. {len(books)} books (by category) -> {args.output}")
        return

    max_pages = 1 if args.test else min(args.pages, 67)
    all_books = []
    session = requests.Session()
    cache_dir = args.cache_dir
    merged_path = args.merged_json or (cache_dir / MERGED_JSON_NAME)

    if args.merge_only:
        # 取得せずキャッシュだけを統合
        all_books = load_all_from_cache(cache_dir, max_pages)
        if not all_books:
            print("No cached data found. Run without --merge-only to fetch pages first.")
            return
        save_merged_json(all_books, merged_path)
        if args.output:
            generate_html(all_books, args.output)
            print(f"HTML: {args.output}")
        return

    for page in range(1, max_pages + 1):
        cpath = cache_path(cache_dir, page)

        # 取得済みならキャッシュから読み込んでスキップ
        if not args.no_cache:
            cached = load_page_cache(cpath)
            if cached is not None:
                all_books.extend(cached)
                print(f"Page {page}/{max_pages}: skip (cached, {len(cached)} items, total: {len(all_books)})")
                continue

        # 取得 → データ抽出 → 保存
        url = build_page_url(BASE_URL, page)
        print(f"Page {page}/{max_pages}: fetching ...")
        html = fetch_page(session, url)
        if not html:
            continue
        if args.debug_html and page == 1:
            args.debug_html.write_text(html, encoding="utf-8")
            print(f"  Debug: saved HTML to {args.debug_html}")
        books = parse_search_page(html)
        if not books and page == 1:
            print("  No results on first page. Amazon may be blocking; try with a browser (Playwright) later.")
        if books:
            save_page_cache(cpath, books)
            print(f"  Saved {len(books)} items -> {cpath}")
        all_books.extend(books)
        print(f"  Total: {len(all_books)}")
        if page < max_pages:
            time.sleep(args.delay)

    if not all_books:
        print("No books collected. Exiting.")
        return

    # 全ページ分のJSONを1ファイルに統合
    save_merged_json(all_books, merged_path)

    # 保存済みデータをまとめて1つのHTMLに出力
    generate_html(all_books, args.output)
    print(f"Done. Total: {len(all_books)} books -> {args.output}")


if __name__ == "__main__":
    main()
