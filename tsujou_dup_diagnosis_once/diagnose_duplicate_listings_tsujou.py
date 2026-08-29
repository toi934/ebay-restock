# -*- coding: utf-8 -*-
"""
タスク1（通常）eBay全出品取得の重複調査 - 読み取り専用診断スクリプト（DRAFT・本番ファイル無変更）
作成: 2026/08/29（戸井さん指示: get_all_listings()の重複取得原因調査）

目的:
  2026/08/29のHARU統合dry-run検証（Run #1）で、合計取得件数18,540件がeBay側報告の
  TotalNumberOfEntries 18,445件を上回り、かつ「除外リスト・variation判定後の母集団」
  （out_of_stockリスト長）4,110件が①のユニークQty=0件数3,003件を上回るという矛盾が判明した。
  本スクリプトは本番 tsujou/ebay_restock.py・senmon/ebay_restock.py と共通の
  get_all_listings()のリクエスト構造・ページングロジック（EntriesPerPage=200・PageNumber
  逐次インクリメント・Sort未指定・終了条件`len(all_items) >= total`）を診断用に複製し
  （ロジック自体は一切変更しない）、以下を read-only で確認する:
    1. GetMyeBaySellingリクエストにSort指定があるか
    2. 実際に返ってきた1ページあたりの件数（リクエストしたEntriesPerPage=200との比較）
    3. 重複しているItem ID数・同一Item IDの最大出現回数
    4. 重複がページ境界（隣接ページ間）で発生しているか、離れたページ間か、同一ページ内か
    5. Qty=0商品に絞った場合の重複状況（①③⑤の矛盾の直接的な原因を特定するため）
    6. 本番0→1処理（out_of_stockリストへのappend→バッチ更新）で同一Item IDへ複数回
       ReviseInventoryStatusが呼ばれる可能性があるかをコードロジック・実データ両面で確認

  ★本番ファイル・PAUSED・schedule・専門版・HARU条件ロジックには一切触れない★
  ★ReviseInventoryStatus・Qty変更・ファイル書き込み（state更新）は一切行わない★
  ★git push・commitステップも持たない（呼び出し側ワークフローで担保）★
  ★このスクリプト自体は取得したデータをファイルへ書き込まず、標準出力にのみ結果を表示する★

使い方: python diagnose_duplicate_listings_tsujou.py
"""
import requests
import xml.etree.ElementTree as ET
import sys
import time
import os
from collections import Counter

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

MAX_RETRIES = 5
RETRY_WAIT_SECONDS = 10
REQUEST_TIMEOUT = 60

TOKEN = os.environ.get("TSUJOU_TOKEN", "")
APP_ID = os.environ.get("APP_ID", "")
DEV_ID = os.environ.get("DEV_ID", "")
CERT_ID = os.environ.get("CERT_ID", "")
API_URL = "https://api.ebay.com/ws/api.dll"


def call_api(call_name, xml_body):
    """★本番ebay_restock.py（通常・専門とも共通）のcall_api()と完全に同一のロジック（無変更でコピー）★"""
    headers = {
        "X-EBAY-API-CALL-NAME": call_name,
        "X-EBAY-API-SITEID": "0",
        "X-EBAY-API-COMPATIBILITY-LEVEL": "967",
        "X-EBAY-API-APP-NAME": APP_ID,
        "X-EBAY-API-DEV-NAME": DEV_ID,
        "X-EBAY-API-CERT-NAME": CERT_ID,
        "Content-Type": "text/xml",
    }
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(API_URL, headers=headers, data=xml_body.encode("utf-8"), timeout=REQUEST_TIMEOUT)
            return resp.text
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = RETRY_WAIT_SECONDS * attempt
                print("  [ネットワークエラー retry " + str(attempt) + "/" + str(MAX_RETRIES - 1) + "] " + str(e)[:100])
                time.sleep(wait)
            else:
                print("  [リトライ上限到達] " + str(e)[:200])
        except requests.exceptions.RequestException as e:
            print("  [非リトライエラー] " + str(e)[:200])
            raise
    raise last_error if last_error else RuntimeError("call_api: 不明なエラー")


def get_all_listings_with_tracking():
    """本番get_all_listings()と完全に同一のリクエストXML・ページングループ構造だが、
    診断のため各Itemについて (page番号, ItemID, QuantityAvailable, Variations有無) を
    全件記録する。ページング方法・EntriesPerPage=200・Sort未指定・ループ終了条件
    `len(all_items) >= total` はいずれも本番と同一（一切変更していない）。"""
    all_items = []
    page_sizes = []
    item_log = []  # (page, item_id, qty_text, has_variations)
    ns = {"ns": "urn:ebay:apis:eBLBaseComponents"}
    page = 1
    reported_total = 0
    while True:
        xml = """<?xml version="1.0" encoding="utf-8"?>
<GetMyeBaySellingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken>""" + TOKEN + """</eBayAuthToken></RequesterCredentials>
  <ActiveList><Include>true</Include><Pagination><EntriesPerPage>200</EntriesPerPage><PageNumber>""" + str(page) + """</PageNumber></Pagination></ActiveList>
  <DetailLevel>ReturnAll</DetailLevel>
</GetMyeBaySellingRequest>"""
        response = call_api("GetMyeBaySelling", xml)
        root = ET.fromstring(response)
        items = root.findall(".//ns:ItemArray/ns:Item", ns)
        if not items:
            break
        page_sizes.append(len(items))
        for item in items:
            item_id_el = item.find("ns:ItemID", ns)
            qty_el = item.find("ns:QuantityAvailable", ns)
            variations_el = item.find("ns:Variations", ns)
            item_id = item_id_el.text if item_id_el is not None else None
            qty_text = qty_el.text if qty_el is not None else None
            item_log.append((page, item_id, qty_text, variations_el is not None))
        all_items.extend(items)
        total_el = root.find(".//ns:ActiveList/ns:PaginationResult/ns:TotalNumberOfEntries", ns)
        reported_total = int(total_el.text) if total_el is not None else 0
        print("取得中... " + str(len(all_items)) + " / " + str(reported_total)
              + " 件（このページ: " + str(len(items)) + "件, page=" + str(page) + "）")
        if len(all_items) >= reported_total:
            break
        page += 1
    return page_sizes, item_log, reported_total


def analyze_duplicates(label, id_list_with_page):
    """id_list_with_page: [(page, item_id), ...] を受け取り重複統計を返す。"""
    ids_only = [iid for (_p, iid) in id_list_with_page if iid]
    total_rows = len(ids_only)
    counter = Counter(ids_only)
    unique_ids = len(counter)
    dup_items = {iid: c for iid, c in counter.items() if c > 1}
    dup_id_count = len(dup_items)
    extra_rows = total_rows - unique_ids

    print("  [" + label + "] 総行数（重複含む）: " + str(total_rows))
    print("  [" + label + "] ユニークItem ID数: " + str(unique_ids))
    print("  [" + label + "] 重複しているItem ID数（2回以上出現）: " + str(dup_id_count))
    print("  [" + label + "] 重複による余剰行数（総行数-ユニーク数）: " + str(extra_rows))

    if dup_items:
        max_count = max(dup_items.values())
        max_ids = [iid for iid, c in dup_items.items() if c == max_count]
        print("  [" + label + "] 同一Item IDの最大出現回数: " + str(max_count)
              + " 回（該当ID例、最大" + str(min(5, len(max_ids))) + "件: " + str(max_ids[:5]) + "）")
        dist = Counter(dup_items.values())
        print("  [" + label + "] 出現回数の分布（出現回数: 該当ID数）: " + str(dict(sorted(dist.items()))))
    else:
        print("  [" + label + "] 同一Item IDの最大出現回数: 該当なし（重複ゼロ）")

    return dup_items


def analyze_page_adjacency(label, item_log, dup_items):
    id_to_pages = {}
    for p, iid, *_ in item_log:
        if iid in dup_items:
            id_to_pages.setdefault(iid, []).append(p)

    same_page = 0
    adjacent_only = 0
    nonadjacent = 0
    sample_lines = []
    for iid, pages in id_to_pages.items():
        pages_sorted = sorted(pages)
        diffs = [b - a for a, b in zip(pages_sorted, pages_sorted[1:])]
        if any(d == 0 for d in diffs):
            same_page += 1
        elif all(d == 1 for d in diffs):
            adjacent_only += 1
        else:
            nonadjacent += 1
        if len(sample_lines) < 15:
            sample_lines.append(str(iid) + ": pages=" + str(pages_sorted))

    print("  [" + label + "] 重複IDのうち「同一ページ内で複数回」出現: " + str(same_page) + " 件")
    print("  [" + label + "] 重複IDのうち「隣接ページ間（差1）のみ」で発生: " + str(adjacent_only) + " 件")
    print("  [" + label + "] 重複IDのうち「2ページ以上離れて」出現: " + str(nonadjacent) + " 件")
    print("  [" + label + "] サンプル（Item ID: 出現ページ一覧、最大15件）:")
    for line in sample_lines:
        print("    - " + line)


def main():
    print("=" * 70)
    print("タスク1（通常）eBay全出品取得 重複調査（読み取り専用診断・DRAFT）")
    print("実行日時: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    print("")
    print("[確認1] GetMyeBaySellingリクエストのSort指定")
    print("  本番get_all_listings()のXMLリクエストには <ActiveList><Sort>...</Sort></ActiveList>")
    print("  に相当する要素は存在しない（Pagination/EntriesPerPage・PageNumberのみ指定）。")
    print("  → ソート順はeBay側のデフォルト実装依存であり、明示的な安定ソート（例:")
    print("    ItemIDを一意なタイブレーカーとしたソート）は指定されていない。")

    print("")
    print("全出品リスト取得中（本番get_all_listings()と同一ロジック・診断用にpage/Qty/Variationsを記録）...")
    page_sizes, item_log, reported_total = get_all_listings_with_tracking()
    total_fetched = len(item_log)

    print("")
    print("-" * 70)
    print("[確認2] ページサイズの実績")
    print("  リクエストしたEntriesPerPage: 200")
    print("  実際に返ってきたページ数: " + str(len(page_sizes)))
    if page_sizes:
        print("  1ページあたりの件数（先頭5ページ）: " + str(page_sizes[:5]))
        print("  1ページあたりの件数（最終5ページ）: " + str(page_sizes[-5:]))
        uniq_sizes = sorted(set(page_sizes))
        print("  出現したページサイズの種類（ユニーク値一覧）: " + str(uniq_sizes))
    print("  合計取得件数: " + str(total_fetched) + " / eBay報告TotalNumberOfEntries: " + str(reported_total))
    print("  差分（合計取得件数 - 報告総数）: " + str(total_fetched - reported_total))

    print("")
    print("-" * 70)
    print("[確認3] 重複Item ID集計（全" + str(total_fetched) + "件対象）")
    all_id_page = [(p, iid) for (p, iid, _q, _v) in item_log]
    dup_all = analyze_duplicates("全件", all_id_page)

    print("")
    print("-" * 70)
    print("[確認4] 重複はページ境界（隣接ページ間）か、離れたページ間か（全件対象）")
    analyze_page_adjacency("全件", item_log, dup_all)

    print("")
    print("-" * 70)
    print("[確認5] Qty=0商品に絞った重複集計（①③⑤の矛盾の直接原因を特定）")
    qty0_id_page = [(p, iid) for (p, iid, q, _v) in item_log if q is not None and q.strip() == "0"]
    print("  Qty=0の行数（重複含む）: " + str(len(qty0_id_page)))
    dup_qty0 = analyze_duplicates("Qty=0", qty0_id_page)
    print("")
    analyze_page_adjacency("Qty=0", [(p, iid, None, None) for (p, iid) in qty0_id_page], dup_qty0)
    qty0_unique = len({iid for (_p, iid) in qty0_id_page})
    print("  → このQty=0ユニークID数（" + str(qty0_unique)
          + "）が、2026/08/29 dry-run結果の①（eBay Qty=0件数）と対応する値である。")

    print("")
    print("-" * 70)
    print("[確認6] 本番0→1処理で同一Item IDを複数回ReviseInventoryStatusする可能性")
    print("  本番ebay_restock.py（通常・専門とも共通ロジック）は、取得したitems一覧を")
    print("  for文でそのまま走査し、Qty=0かつ除外リスト非該当かつVariations無しの商品を")
    print("  out_of_stockリストへID重複排除なしでappendする。続くQty更新ループも")
    print("  out_of_stockリストをそのままBATCH_SIZE=4でバッチ処理するため、")
    print("  同一Item IDがitems一覧に複数回含まれていれば、out_of_stockにも複数回appendされ、")
    print("  結果として同一Item IDへ複数回ReviseInventoryStatusが呼ばれる構造上の可能性が")
    print("  【ある】（コードレビューによる確認）。")
    if dup_qty0:
        print("  → 今回の実データでも、Qty=0商品に重複が実際に" + str(len(dup_qty0))
              + "件確認されており（[確認5]参照）、除外リスト・Variations条件を通過した")
        print("    場合はこれらが実際に複数回ReviseInventoryStatus対象になり得る状態である。")
    else:
        print("  → 今回の実データではQty=0商品に重複は確認されなかった（[確認5]参照）。")

    print("")
    print("=" * 70)
    print("★診断完了★（読み取り専用。Qty変更・ファイル書き込み・git push は一切行っていません）")
    print("=" * 70)


if __name__ == "__main__":
    main()
