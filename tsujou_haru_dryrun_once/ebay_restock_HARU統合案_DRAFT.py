# -*- coding: utf-8 -*-
"""
★★★ DRAFT・未適用・本番ファイルではありません ★★★
タスク1（通常アカウント）ebay_restock.py に「HARU在庫あり(S列=1)条件」を
追加した統合案。2026/08/29、戸井さん承認の方針に基づく検証用コード変更案。

ベース: ﾀｽｸ1_github_actions\\tsujou\\ebay_restock.py
        （このDRAFTフォルダ内の ebay_restock_ORIGINAL_REFERENCE.py と同一内容）

変更点は「HARU在庫あり条件の追加」ブロックのみ。それ以外（除外リスト読み込み、
variation判定、--limit適用、--dry-run、確認プロンプト、ReviseInventoryStatus
呼び出し、失敗処理・auto_excluded_ids.txt追記、リトライ・ネットワークエラー処理）は
すべて元のロジックをそのまま維持している（文言・実装とも無変更）。

このDRAFTでのみ変更した箇所（本番ファイルには反映していない）:
  1. 冒頭に haru_s1_select_tsujou（同フォルダ内の新規モジュール）のimportを追加
  2. ★PAUSED = False にしている（検証用。本番の tsujou/ebay_restock.py は
     引き続き PAUSED = True のまま・一切変更していない）★
  3. out_of_stock 構築直後・--limit適用前に、HARU S列=1条件によるAND絞り込みを追加
     （①eBay Qty=0件数 ②HARU S列=1との一致件数 ⑤HARU対象外による除外件数を表示）

HARU在庫判定ルール（2026/08/09戸井さん確定・絶対厳守）:
  S列（0-indexed 18列目）が整数の1の商品のみ「在庫あり」。J列は一切見ない。
  HARUにItem IDが無い・S列=0・S列を正常に読めない商品はすべて更新禁止
  （haru_s1_select_tsujou.load_haru_s1_item_ids が安全側に実装済み）。

Qty更新方向は0→1のみ。1→0処理はこのDRAFTにも存在しない（元から無い）。
"""
import requests
import xml.etree.ElementTree as ET
import sys
import time
import os

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ★DRAFT追加: 同フォルダ内の haru_s1_select_tsujou を import
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
from haru_s1_select_tsujou import (  # noqa: E402
    find_latest_haru_file_tsujou,
    load_haru_s1_item_ids,
    HaruTsujouFileNotFoundError,
)

# ネットワークリトライ設定
MAX_RETRIES = 5
RETRY_WAIT_SECONDS = 10
REQUEST_TIMEOUT = 60

# GitHub Secrets（環境変数）から読み込み
TOKEN  = os.environ.get("TSUJOU_TOKEN", "")
APP_ID = os.environ.get("APP_ID", "")
DEV_ID = os.environ.get("DEV_ID", "")
CERT_ID= os.environ.get("CERT_ID", "")
API_URL = "https://api.ebay.com/ws/api.dll"

BATCH_SIZE = 4

# 手動除外リスト（固定）★元のebay_restock.pyと同一（無変更）★
EXCLUDE_IDS = [
    "196342327649",
    "195659104708",
    "195660529828",
    "195660529829",
    "195659105383",
    "196620760308",
    "196620741958",
    "198039851302",
    "197342847508",
    "197716946712",
    "197743262834",
    "198149818988",
    "197505044847",
]

# auto_excluded_ids.txt はスクリプトと同じディレクトリ
AUTO_EXCLUDE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auto_excluded_ids.txt")


def call_api(call_name, xml_body):
    """eBay Trading API呼び出し（ネットワークエラー時に自動リトライ）"""
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
            resp = requests.post(
                API_URL,
                headers=headers,
                data=xml_body.encode("utf-8"),
                timeout=REQUEST_TIMEOUT,
            )
            return resp.text
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = RETRY_WAIT_SECONDS * attempt
                print("  [ネットワークエラー retry " + str(attempt) + "/" + str(MAX_RETRIES - 1) + "] " + str(e)[:100])
                print("  " + str(wait) + " 秒待機後リトライします...")
                time.sleep(wait)
            else:
                print("  [リトライ上限到達] " + str(e)[:200])
        except requests.exceptions.RequestException as e:
            print("  [非リトライエラー] " + str(e)[:200])
            raise
    raise last_error if last_error else RuntimeError("call_api: 不明なエラー")


def get_all_listings():
    # ★Fix B(2026/08/30確定・戸井さん承認・タスク8工程1): ページング終了判定を
    # 「重複込みの累計取得件数」ではなく「ユニークItem ID数」基準に変更。
    # あわせて無限ループ防止の安全上限(MAX_PAGES)を追加。Fix C(Sort指定)は今回は
    # 触らない。全出品を1回で丸ごと取得する既存の全体構造は変更していない。
    all_items = []
    unique_ids_seen = set()
    page = 1
    MAX_PAGES = 150
    ns = {"ns": "urn:ebay:apis:eBLBaseComponents"}
    total = 0
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
        all_items.extend(items)
        for _it in items:
            _id_el = _it.find("ns:ItemID", ns)
            if _id_el is not None and _id_el.text:
                unique_ids_seen.add(_id_el.text)
        total_el = root.find(".//ns:ActiveList/ns:PaginationResult/ns:TotalNumberOfEntries", ns)
        total = int(total_el.text) if total_el is not None else 0
        print("取得中... 累計(重複込み) " + str(len(all_items)) + " 件 / ユニーク " + str(len(unique_ids_seen)) + " 件 / 報告総数 " + str(total) + " 件（ページ" + str(page) + "）")
        if len(unique_ids_seen) >= total:
            print("[Fix B] ユニークItem ID数(" + str(len(unique_ids_seen)) + ")が報告総数(" + str(total) + ")に到達したため終了します。")
            break
        if page >= MAX_PAGES:
            print("[Fix B 安全上限到達] MAX_PAGES=" + str(MAX_PAGES) + " に達したため強制終了します。ユニーク " + str(len(unique_ids_seen)) + " / 報告総数 " + str(total) + " 件（未到達の可能性あり・要調査）。")
            break
        page += 1
    print("[Fix B 最終結果] 累計(重複込み) " + str(len(all_items)) + " 件 / ユニーク " + str(len(unique_ids_seen)) + " 件 / 報告総数 " + str(total) + " 件 / 一致: " + str(len(unique_ids_seen) == total))
    return all_items


def log_failure(item_id, reason):
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "failed_items.log"), "a", encoding="utf-8") as f:
            f.write(item_id + "\t" + reason + "\n")
    except Exception:
        pass


def load_auto_excluded():
    """auto_excluded_ids.txt から自動除外IDをロード（無ければ空リスト）"""
    try:
        with open(AUTO_EXCLUDE_FILE, "r", encoding="utf-8") as f:
            ids = set()
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                item_id = stripped.split("\t")[0].strip()
                if item_id:
                    ids.add(item_id)
            return ids
    except FileNotFoundError:
        return set()
    except Exception as e:
        print("auto_excluded_ids.txt 読み込みエラー: " + str(e))
        return set()


def add_auto_excluded(item_id, reason):
    """item_id を auto_excluded_ids.txt に追記（理由をコメントとして記録）"""
    try:
        with open(AUTO_EXCLUDE_FILE, "a", encoding="utf-8") as f:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(item_id + "\t# " + timestamp + " " + reason[:100] + "\n")
        print("  → AUTO_EXCLUDE に追加: " + item_id)
    except Exception as e:
        print("auto_excluded_ids.txt 書き込みエラー: " + str(e))


def is_permanent_error(reason):
    """このエラーは恒久的か（再試行不要）？"""
    r = (reason or "").lower()
    permanent_keywords = [
        "ended", "not allowed to revise an ended", "item ended",
        "auction has ended", "listing has ended",
        "item not found", "invalid itemid",
    ]
    return any(k in r for k in permanent_keywords)


def update_quantity_single(item_id):
    xml = """<?xml version="1.0" encoding="utf-8"?>
<ReviseInventoryStatusRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken>""" + TOKEN + """</eBayAuthToken></RequesterCredentials>
  <InventoryStatus><ItemID>""" + item_id + """</ItemID><Quantity>1</Quantity></InventoryStatus>
</ReviseInventoryStatusRequest>"""
    result = call_api("ReviseInventoryStatus", xml)
    try:
        root = ET.fromstring(result)
        ns = {"ns": "urn:ebay:apis:eBLBaseComponents"}
        ack_el = root.find("ns:Ack", ns)
        ack = ack_el.text if ack_el is not None else "Unknown"
        if ack in ("Success", "Warning"):
            print("成功: " + item_id)
            return True
        short_msg_el = root.find(".//ns:Errors/ns:ShortMessage", ns)
        long_msg_el = root.find(".//ns:Errors/ns:LongMessage", ns)
        reason = (short_msg_el.text if short_msg_el is not None else "") + " | " + (long_msg_el.text if long_msg_el is not None else "")
        reason_clean = reason.strip(" |")
        print("失敗: " + item_id + " (" + reason_clean + ")")
        log_failure(item_id, reason_clean)
        if is_permanent_error(reason_clean):
            add_auto_excluded(item_id, reason_clean)
        return False
    except Exception as e:
        print("失敗: " + item_id + " (解析エラー: " + str(e) + ")")
        log_failure(item_id, "解析エラー: " + str(e))
        return False


def update_quantity_batch(item_ids):
    inventory_xml = ""
    for item_id in item_ids:
        inventory_xml += "<InventoryStatus><ItemID>" + item_id + "</ItemID><Quantity>1</Quantity></InventoryStatus>"
    xml = """<?xml version="1.0" encoding="utf-8"?>
<ReviseInventoryStatusRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken>""" + TOKEN + """</eBayAuthToken></RequesterCredentials>
""" + inventory_xml + """
</ReviseInventoryStatusRequest>"""
    result = call_api("ReviseInventoryStatus", xml)

    try:
        root = ET.fromstring(result)
        ns = {"ns": "urn:ebay:apis:eBLBaseComponents"}
        ack_el = root.find("ns:Ack", ns)
        ack = ack_el.text if ack_el is not None else "Unknown"
    except Exception:
        success_count = 0
        fail_count = 0
        for item_id in item_ids:
            if update_quantity_single(item_id):
                success_count += 1
            else:
                fail_count += 1
        return success_count, fail_count

    if ack in ("Success", "Warning"):
        for item_id in item_ids:
            print("成功: " + item_id)
        return len(item_ids), 0
    elif ack == "PartialFailure":
        success_ids = set()
        for inv_status in root.findall(".//ns:InventoryStatus", ns):
            id_el = inv_status.find("ns:ItemID", ns)
            if id_el is not None and id_el.text:
                success_ids.add(id_el.text)
        success_count = 0
        fail_count = 0
        for item_id in item_ids:
            if item_id in success_ids:
                print("成功: " + item_id)
                success_count += 1
            else:
                if update_quantity_single(item_id):
                    success_count += 1
                else:
                    fail_count += 1
        return success_count, fail_count
    else:
        print("  [バッチ全体失敗 → 1件ずつリトライ]")
        success_count = 0
        fail_count = 0
        for item_id in item_ids:
            if update_quantity_single(item_id):
                success_count += 1
            else:
                fail_count += 1
        return success_count, fail_count


def parse_limit():
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--limit="):
            try:
                return int(arg.split("=", 1)[1])
            except ValueError:
                return None
        if arg == "--limit" and i + 1 < len(sys.argv):
            try:
                return int(sys.argv[i + 1])
            except ValueError:
                return None
    return None


# ★★★ 一時停止フラグ ★★★
# ★DRAFTのみFalse。本番 tsujou/ebay_restock.py の PAUSED=True は変更していない★
PAUSED = False

def main():
    if PAUSED:
        print("[PAUSED] 在庫切れキャンセル急増の原因調査のため一時停止中です。処理はスキップされました。")
        print("[PAUSED] 再開するには ebay_restock.py の PAUSED = True を False に変更してください。")
        return

    dry_run = "--dry-run" in sys.argv
    auto_yes = "--yes" in sys.argv
    limit = parse_limit()

    print("=" * 50)
    print("eBay 在庫補充スクリプト 開始 [アカウント: 通常 japanesehappinessshop]（★HARU統合DRAFT★）")
    if dry_run:
        print("[DRY RUN モード: 更新は行いません]")
    if limit is not None:
        print("[LIMIT 設定: 今回は最大 " + str(limit) + " 件まで処理]")

    auto_excluded = load_auto_excluded()
    all_excluded_set = set(EXCLUDE_IDS) | auto_excluded
    print("除外IDロード: 手動 " + str(len(EXCLUDE_IDS)) + " 件 + 自動 " + str(len(auto_excluded)) + " 件 = 計 " + str(len(all_excluded_set)) + " 件")

    print("全出品リスト取得中...")
    items = get_all_listings()
    print("合計取得件数（重複込み・生データ）: " + str(len(items)) + " 件")
    ns = {"ns": "urn:ebay:apis:eBLBaseComponents"}
    out_of_stock = []
    excluded = []
    skipped_variations = []
    seen_processed_ids = set()  # ★Fix A(2026/08/30確定・戸井さん承認・タスク8工程1): Item ID重複処理防止★
    duplicate_skip_count = 0
    for item in items:
        item_id_el = item.find("ns:ItemID", ns)
        item_id = item_id_el.text if item_id_el is not None else None
        if item_id is None:
            continue
        if item_id in seen_processed_ids:
            duplicate_skip_count += 1
            continue
        seen_processed_ids.add(item_id)
        qty_el = item.find("ns:QuantityAvailable", ns)
        title_el = item.find("ns:Title", ns)
        variations_el = item.find("ns:Variations", ns)
        if qty_el is not None:
            if int(qty_el.text) == 0:
                title = title_el.text if title_el is not None else "不明"
                if item_id in all_excluded_set:
                    excluded.append({"id": item_id, "title": title})
                elif variations_el is not None:
                    skipped_variations.append({"id": item_id, "title": title})
                else:
                    out_of_stock.append({"id": item_id, "title": title})
    print("[Fix A] 重複ItemIDによりスキップした件数: " + str(duplicate_skip_count) + " 件 / 処理したユニークItemID数: " + str(len(seen_processed_ids)) + " 件")

    # ============================================================
    # ★DRAFT新規追加: HARU在庫あり(S列=1)条件によるAND絞り込み★
    # 2026/08/29 戸井さん承認の方針。out_of_stock構築直後・--limit適用前に実施。
    # 既存の除外リスト判定・variation判定には一切手を加えていない（上のfor文は無変更）。
    # ============================================================
    all_qty0_ids = (
        {it["id"] for it in out_of_stock}
        | {it["id"] for it in excluded}
        | {it["id"] for it in skipped_variations}
    )
    ebay_qty0_total = len(all_qty0_ids)  # ①eBay Qty=0件数（全体・除外リスト等考慮前）

    haru_dir = os.environ.get("HARU_XLSX_DIR", os.path.dirname(os.path.abspath(__file__)))
    try:
        haru_path, haru_info = find_latest_haru_file_tsujou(haru_dir)
        haru_s1_ids, haru_total_rows = load_haru_s1_item_ids(haru_path)
    except HaruTsujouFileNotFoundError as e:
        print("[HARU安全停止] " + str(e))
        print("HARUファイルを安全に一意特定できないため、更新対象を確定できません。")
        print("安全のため処理を中止します（Qty更新は一切行っていません）。")
        print("=" * 50)
        return

    haru_match_raw = all_qty0_ids & haru_s1_ids  # ②eBay Qty=0 と HARU S列=1 の一致（除外リスト等考慮前）

    pre_haru_out_of_stock = out_of_stock  # 除外リスト・variation判定後、HARU判定前
    out_of_stock = [it for it in pre_haru_out_of_stock if it["id"] in haru_s1_ids]
    haru_excluded = [it for it in pre_haru_out_of_stock if it["id"] not in haru_s1_ids]  # ⑤

    print("-" * 50)
    print("[HARU] 使用ファイル: " + os.path.basename(haru_path) + "（" + haru_info["source"] + "）")
    print("[HARU] 全行数: " + str(haru_total_rows) + " / S列(eBay Qty)=1 の件数: " + str(len(haru_s1_ids)))
    print("① eBay Qty=0 件数（全体・除外リスト等考慮前）: " + str(ebay_qty0_total))
    print("② eBay Qty=0 と HARU S列=1 の一致件数（除外リスト等考慮前・参考値）: " + str(len(haru_match_raw)))
    print("   （除外リスト・variation判定後の母集団）: " + str(len(pre_haru_out_of_stock)) + " 件")
    print("⑤ HARU対象外により除外された件数（除外リスト・variation判定後の母集団のうち）: " + str(len(haru_excluded)))
    print("-" * 50)

    if excluded:
        manual_count = sum(1 for it in excluded if it["id"] in EXCLUDE_IDS)
        auto_count = len(excluded) - manual_count
        print("除外された商品: " + str(len(excluded)) + " 件 (手動:" + str(manual_count) + " / 自動:" + str(auto_count) + ")")
        for item in excluded:
            if item["id"] in EXCLUDE_IDS:
                print("  除外(手動): " + item["id"] + " | " + item["title"])

    if skipped_variations:
        print("スキップ（バリエーション付き）: " + str(len(skipped_variations)) + " 件")

    print("在庫0の商品（HARU在庫あり一致後・最終更新対象）: " + str(len(out_of_stock)) + " 件")  # ③
    if not out_of_stock:
        print("更新対象の商品はありません。終了。")
        print("=" * 50)
        return

    if limit is not None and len(out_of_stock) > limit:
        print("[制限適用] 今回は先頭の " + str(limit) + " 件のみ処理します。")
        print("[残り] " + str(len(out_of_stock) - limit) + " 件は次回以降に処理されます。")
        out_of_stock = out_of_stock[:limit]

    if dry_run:
        print("④ 最終候補Item ID一覧:")
        for item in out_of_stock:
            print("- " + item["id"] + " | " + item["title"])
        print("[DRY RUN] 上記の対象は実際には更新されません。")
        print("=" * 50)
        return

    if not auto_yes:
        confirm = input("続行しますか？ (y/n): ")
        if confirm.strip().lower() != "y":
            print("キャンセル。")
            return

    success = 0
    fail = 0
    network_errors = 0
    total_batches = (len(out_of_stock) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(out_of_stock), BATCH_SIZE):
        batch = out_of_stock[i:i + BATCH_SIZE]
        batch_ids = [item["id"] for item in batch]
        batch_num = i // BATCH_SIZE + 1
        print("[バッチ " + str(batch_num) + "/" + str(total_batches) + "] " + str(len(batch_ids)) + " 件処理中...")
        try:
            s, f = update_quantity_batch(batch_ids)
            success += s
            fail += f
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            print("  [バッチ全体ネットワークエラー] " + str(e)[:200])
            for item_id in batch_ids:
                log_failure(item_id, "ネットワークエラー: " + str(e)[:100])
                print("失敗: " + item_id + " (ネットワーク)")
            fail += len(batch_ids)
            network_errors += 1
            if network_errors >= 3:
                print("  [警告] ネットワークエラーが連続しています。30秒待機します...")
                time.sleep(30)
                network_errors = 0
        except Exception as e:
            print("  [バッチ全体予期しないエラー] " + str(e)[:200])
            for item_id in batch_ids:
                log_failure(item_id, "予期しないエラー: " + str(e)[:100])
            fail += len(batch_ids)

    print("=" * 50)
    print("完了 成功: " + str(success) + " / 失敗: " + str(fail))
    print("在庫0: " + str(len(out_of_stock)) + "件 → 成功: " + str(success) + " / 失敗: " + str(fail))
    print("=" * 50)


main()
