import requests
import xml.etree.ElementTree as ET
import sys
import time
import os

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ネットワークリトライ設定
MAX_RETRIES = 5
RETRY_WAIT_SECONDS = 10
REQUEST_TIMEOUT = 60

# GitHub Secrets（環境変数）から読み込み
TOKEN  = os.environ.get("SENMON_TOKEN", "")
APP_ID = os.environ.get("APP_ID", "")
DEV_ID = os.environ.get("DEV_ID", "")
CERT_ID= os.environ.get("CERT_ID", "")
API_URL = "https://api.ebay.com/ws/api.dll"

# 手動除外リスト（固定）
EXCLUDE_IDS = [
    "375398678929",
    "375794633937",
    "376107013560",
    "375379992775",
    "376585296171",
    "374991482370",
    "375382565039",
    "375290702023",
    "376432852808",
    "376748552363",
    "376571454468",
    "375611822728",
    "375611716482",
    "376602409428",
    "375610376836",
    "376581734488",
    "374979013436",
    "377053733390",
    "376590272040",
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
    all_items = []
    page = 1
    while True:
        xml = """<?xml version="1.0" encoding="utf-8"?>
<GetMyeBaySellingRequest xmlns="urn:ebay:apis:eBLBaseComponents">
  <RequesterCredentials><eBayAuthToken>""" + TOKEN + """</eBayAuthToken></RequesterCredentials>
  <ActiveList><Include>true</Include><Pagination><EntriesPerPage>200</EntriesPerPage><PageNumber>""" + str(page) + """</PageNumber></Pagination></ActiveList>
  <DetailLevel>ReturnAll</DetailLevel>
</GetMyeBaySellingRequest>"""
        response = call_api("GetMyeBaySelling", xml)
        root = ET.fromstring(response)
        ns = {"ns": "urn:ebay:apis:eBLBaseComponents"}
        items = root.findall(".//ns:ItemArray/ns:Item", ns)
        if not items:
            break
        all_items.extend(items)
        total_el = root.find(".//ns:ActiveList/ns:PaginationResult/ns:TotalNumberOfEntries", ns)
        total = int(total_el.text) if total_el is not None else 0
        print("取得中... " + str(len(all_items)) + " / " + str(total) + " 件")
        if len(all_items) >= total:
            break
        page += 1
    return all_items


def load_auto_excluded():
    """auto_excluded_ids.txt から自動除外IDをロード"""
    try:
        with open(AUTO_EXCLUDE_FILE, "r", encoding="utf-8") as f:
            ids = set()
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    ids.add(stripped.split('\t')[0].strip())
            return ids
    except FileNotFoundError:
        return set()
    except Exception as e:
        print("auto_excluded_ids.txt 読み込みエラー: " + str(e))
        return set()


def add_auto_excluded(item_id, reason):
    """item_id を auto_excluded_ids.txt に追記"""
    try:
        with open(AUTO_EXCLUDE_FILE, "a", encoding="utf-8") as f:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(item_id + "\t# " + timestamp + " " + reason[:100] + "\n")
        print("  → AUTO_EXCLUDE に追加: " + item_id)
    except Exception as e:
        print("auto_excluded_ids.txt 書き込みエラー: " + str(e))


def is_permanent_error(reason):
    """このエラーは恒久的か？"""
    r = (reason or "").lower()
    permanent_keywords = [
        "ended", "not allowed to revise an ended", "item ended",
        "auction has ended", "listing has ended",
        "item not found", "invalid itemid",
    ]
    return any(k in r for k in permanent_keywords)


def update_quantity(item_id):
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
        if is_permanent_error(reason_clean):
            add_auto_excluded(item_id, reason_clean)
        return False
    except Exception as e:
        if "Failure" in result:
            print("失敗: " + item_id)
            return False
        print("成功: " + item_id)
        return True


def main():
    dry_run = "--dry-run" in sys.argv
    auto_yes = "--yes" in sys.argv

    print("=" * 50)
    print("eBay 在庫補充スクリプト 開始 [アカウント: 専門 japanese_selectshop]")
    if dry_run:
        print("[DRY RUN モード: 更新は行いません]")

    # 自動除外リストをロード
    auto_excluded = load_auto_excluded()
    all_excluded_set = set(EXCLUDE_IDS) | auto_excluded
    print("除外IDロード: 手動 " + str(len(EXCLUDE_IDS)) + " 件 + 自動 " + str(len(auto_excluded)) + " 件 = 計 " + str(len(all_excluded_set)) + " 件")

    print("全出品リスト取得中...")
    items = get_all_listings()
    print("合計取得件数: " + str(len(items)) + " 件")
    ns = {"ns": "urn:ebay:apis:eBLBaseComponents"}
    out_of_stock = []
    excluded = []
    for item in items:
        qty_el = item.find("ns:QuantityAvailable", ns)
        item_id_el = item.find("ns:ItemID", ns)
        title_el = item.find("ns:Title", ns)
        if qty_el is not None and item_id_el is not None:
            if int(qty_el.text) == 0:
                item_id = item_id_el.text
                title = title_el.text if title_el is not None else "不明"
                if item_id in all_excluded_set:
                    excluded.append({"id": item_id, "title": title})
                else:
                    out_of_stock.append({"id": item_id, "title": title})

    if excluded:
        manual_count = sum(1 for it in excluded if it["id"] in EXCLUDE_IDS)
        auto_count = len(excluded) - manual_count
        print("除外された商品: " + str(len(excluded)) + " 件 (手動:" + str(manual_count) + " / 自動:" + str(auto_count) + ")")

    print("在庫0の商品（更新対象）: " + str(len(out_of_stock)) + " 件")
    if not out_of_stock:
        print("更新対象の商品はありません。終了。")
        print("=" * 50)
        return

    if dry_run:
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
    for item in out_of_stock:
        if update_quantity(item["id"]):
            success += 1
        else:
            fail += 1

    print("=" * 50)
    print("完了 成功: " + str(success) + " / 失敗: " + str(fail))
    print("在庫0: " + str(len(out_of_stock)) + "件 → 成功: " + str(success) + " / 失敗: " + str(fail))
    print("=" * 50)


main()
