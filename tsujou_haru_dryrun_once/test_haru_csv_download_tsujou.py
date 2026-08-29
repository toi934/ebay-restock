# -*- coding: utf-8 -*-
"""
タスク8: HARU（通常アカウント）CSVダウンロード単体実行テスト専用スクリプト
（★カンマ区切りCSV〈csv01〉を実際に1回だけダウンロードします★）

目的:
  probe_haru_csv_menu_tsujou.py（2026/08/21④・調査専用）で確認済みの以下のDOM構造を前提に、
  通常アカウントHARUの「CSVダウンロード（カンマ区切り）」を実際に1回だけ実行し、ダウンロード
  されたCSVをタスク8フォルダ内のテスト用ファイルへ保存、内容の基本検証（読み取り専用）まで
  行う専用テストスクリプト。

  確認済みDOM構造（probe_haru_csv_menu_tsujou_結果.txt 2026-08-22実行分より）:
    - メニュー起点: 完全一致「CSVダウンロード」、onclick="showCsvdown(1);return false;"
    - showCsvdown(1) は id="CsvdownClose1" のdisplayを切り替える
    - CsvdownClose1 内部（表示状態=True確認済み）:
        カンマ区切り: <form name="csv01" action="csvdown_pdo.php" method="POST">
                      <a href="javascript:document.csv01.submit()"
                         onclick="return confirm('HARUの登録データを全てCSVファイル
                         (カンマ区切り)へダウンロードします。\nよろしいですか？')">
                      CSVダウンロード(カンマ区切り)</a></form>
        タブ区切り  : 同様の構造で form name="csv02"（★今回は一切触れない★）

  ★このスクリプトは既存の probe_haru_csv_menu_tsujou.py を一切変更せず、新規ファイルとして
    作成した（probe側の調査専用フローとは完全に別のファイル）。

★★★ 今回実行してよい操作（これだけ・実装確認済み） ★★★
  1. haru_config_tsujou.py の情報で通常HARUへログイン
  2. ログイン成功確認（test_haru_login_tsujou.py と同一判定基準）
  3. 「CSVダウンロード」メニュー起点への1回のクリック（メニューを開く）
  4. CsvdownClose1 の存在・表示状態の確認
  5. CsvdownClose1 内部の form[name="csv01"] の action/method 確認
  6. CsvdownClose1 内部の csv01用アンカー（href="javascript:document.csv01.submit()"）
     への1回だけのクリック（★今回許可された実ダウンロードクリックはこれだけ★）
  7. そのクリックで発生する確認ダイアログ（confirm、文面に「カンマ区切り」を含み
     「タブ区切り」を含まないことを確認したものだけ）を1回だけ受諾
  8. 発生したダウンロードイベントを1回だけ待機・保存
  9. 保存したCSVの読み取り専用の基本検証（9項目）

★★★ 今回絶対に行わないこと（実装確認済み） ★★★
  - csv02（タブ区切り）への操作（クリック・確認ダイアログ受諾等）は一切行わない
    （csv02のアンカー・formには一切アクセスしない。selectorも csv01 専用に限定）
  - problem1〜problem6 等、他のformのクリック・submitは一切行わない
  - CSV→xlsx変換
  - 候補抽出（extract_candidates_*.py 等）の実行・呼び出し
  - eBay API呼び出し（GetItem・ReviseInventoryStatus・ReviseItem・Inventory API等）
  - Qty変更
  - 既存ファイルへの書き込み・上書き
    （xlsx・extract_by_qty_progress*.csv・update_log.txt・manual_excluded_ids_master.txt・
    候補抽出結果txt はいずれも一切開かない・書き込まない・呼び出さない）
  - 既存のタスク8スクリプト（probe_haru_csv_menu_tsujou.py・check_candidates.py・
    extract_candidates_by_qty_column.py・extract_candidates_senmon.py・
    update_qty_single.py・update_qty_batch21.py・update_qty_batch4.py 等）の変更・呼び出し
  - Windowsタスクスケジューラへの登録・自動実行化
  - 専門アカウント（japanese_selectshop）関連の処理
  - document全体・ページ全体を対象にしたa/button/input等の総当たり列挙
    （CsvdownClose1・csv01formの確認はいずれも document.getElementById() で対象を直接取得し、
    その内部だけをquerySelectorAllする設計。document全体へのquerySelectorAllは行わない）
  - スクリーンショットの保存

★★★ 秘密情報の保護（test_haru_login_tsujou.py / probe_haru_csv_menu_tsujou.py と同方針） ★★★
  - HARU_USER_ID / HARU_PASSWORD をログ・結果txt・コンソールのどこにも出力しない
  - Cookie・session storage・local storage・storage_state は一切取得・保存しない
    （context.cookies() / context.storage_state() は一切呼ばない）
  - ページのHTML全文は保存しない（page.content() は一切呼ばない）
  - URLをログに出す場合は必ずクエリ文字列・フラグメントを除去してから出力する
  - 確認ダイアログの本文（confirmのメッセージ）はログに出力するが、これはHARU側が
    表示する定型文言でありID/PW/Cookie等の秘密情報は含まれない
  - onclick等の属性値は万一長大な場合に備えログ出力を最大300文字に切り詰める

安全停止条件（該当時は推測で先へ進まず、分かったところまで報告して停止する）:
  1. ログインに失敗した場合（判定基準は test_haru_login_tsujou.py と同一）
  2. 「CSVダウンロード」メニュー起点の可視候補が1件に絞れない場合
  3. メニューを安全に開けない場合（クリックに失敗する等）
  4. document.getElementById("CsvdownClose1") が見つからない、または表示状態と
     判定できない場合
  5. CsvdownClose1内部に form[name="csv01"] がちょうど1件存在しない場合
     （0件または2件以上）
  6. csv01のaction/methodが想定（csvdown_pdo.php / POST）と異なる場合
  7. CsvdownClose1内部に「csv01」用アンカー（href="javascript:document.csv01.submit()"）
     がちょうど1件存在しない場合
  8. アンカーのonclickに「カンマ区切り」を含む確認ダイアログの痕跡が確認できない場合
  9. クリック後に発生した確認ダイアログが、想定外のタイミング／種別／文言だった場合
     （このスクリプトが自らアンカーをクリックした直後の一瞬だけを「受諾してよい区間」とし、
     それ以外のタイミングで発生したダイアログ、type!="confirm"のダイアログ、文言に
     「カンマ区切り」を含まない・「タブ区切り」を含むダイアログは、いずれも受諾せず
     dismissして停止する）
  10. ダウンロードイベントが複数発生した場合（2件目以降は即キャンセルし異常終了）
  11. 予期しない新規タブ/ポップアップが発生した場合（即クローズして停止）
  12. ダウンロードが既定時間内に完了しない場合（タイムアウト）
  13. ダウンロードの失敗（download.failure()がNoneでない）を検出した場合
  14. 保存先ファイル名が既に存在する場合（上書きせず安全停止）
  15. 保存したCSVの基本検証（9項目）のいずれか1つでも満たさない場合
      （この場合もファイル自体は削除せず保持するが、「ダウンロード成功」とは扱わない）

CSV保存先:
  タスク8フォルダ直下（このスクリプトと同じフォルダ）に、
  "haru_download_test_tsujou_YYYYMMDD_HHMMSS.csv" の形式でテスト用ファイル名として保存する。
  既存のxlsx・progress CSV・update_log.txt・manual_excluded_ids_master.txt・候補抽出結果txtは
  一切上書きしない。

CSV基本検証（読み取り専用・9項目）:
  1. ファイルが存在する
  2. ファイルサイズが0ではない
  3. cp932で読み取れる
  4. ヘッダー行が存在する
  5. 列数が20列
  6. 「eBay Item Number」列が存在する
  7. 18列目（0-indexed。S列相当）が「eBay Qty」
  8. データ行が0件ではない
  9. Item ID先頭が「1」の行が過半数（多数派）→ 通常アカウント用CSVと判断

使い方（戸井さんの承認後、戸井さんのPC上で実行）:
  python test_haru_csv_download_tsujou.py
"""

import csv
import os
import sys
import time
from urllib.parse import urlsplit, urlunsplit

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import haru_config_tsujou as haru_config  # noqa: E402

RESULT_TXT = os.path.join(_THIS_DIR, "test_haru_csv_download_tsujou_結果.txt")

PAGE_TIMEOUT_MS = 30000
POST_LOGIN_WAIT_MS = 20000
MENU_OPEN_WAIT_MS = 4000
DOWNLOAD_TIMEOUT_MS = 60000

ATTR_VALUE_MAX_LEN = 300

TOP_MARKER_TEXT = "CSVダウンロード"        # ログイン確認用の目印（部分一致で存在確認のみ）
MENU_TRIGGER_TEXT = "CSVダウンロード"       # メニューを開くトリガー候補（完全一致で探索）

CSVDOWN_CONTAINER_ID = "CsvdownClose1"

TARGET_FORM_NAME = "csv01"
TARGET_FORM_ACTION = "csvdown_pdo.php"
TARGET_FORM_METHOD = "POST"
TARGET_HREF = "javascript:document.csv01.submit()"
TARGET_DIALOG_MUST_CONTAIN = "カンマ区切り"
TARGET_DIALOG_MUST_NOT_CONTAIN = "タブ区切り"

EXPECTED_COLUMN_COUNT = 20
EXPECTED_ITEM_COL_NAME = "eBay Item Number"
EXPECTED_QTY_COL_INDEX = 18  # 0-indexed（S列相当）
EXPECTED_QTY_COL_NAME = "eBay Qty"
ITEM_ID_NORMAL_PREFIX = "1"
ITEM_ID_MAJORITY_RATIO = 0.5


def _strip_query(url):
    """URLからクエリ文字列・フラグメントを除去する（セッショントークン等の漏洩防止）。"""
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return "(URL解析失敗)"


def _truncate(s, n=ATTR_VALUE_MAX_LEN):
    if s is None:
        return None
    s = str(s)
    if len(s) > n:
        return s[:n] + "...(truncated)"
    return s


def _describe_element(el, log, label):
    """要素の最小限のDOM情報のみをログへ出力する（HTML全文は取得しない）。
    probe_haru_csv_menu_tsujou.py と同一ロジック（コピーであり、probe側は未変更）。"""
    try:
        tag = el.evaluate("e => e.tagName")
    except Exception:
        tag = "(取得失敗)"
    try:
        text = (el.inner_text() or "").strip()
    except Exception:
        text = ""
    try:
        onclick = el.get_attribute("onclick")
    except Exception:
        onclick = None
    try:
        visible = el.is_visible()
    except Exception:
        visible = "(取得失敗)"

    log("  [" + label + "]")
    log("    tag        : " + str(tag))
    log("    text       : " + str(text))
    log("    visible    : " + str(visible))
    log("    onclick    : " + str(_truncate(onclick)))


# ★CsvdownClose1自体の存在・表示状態だけを確認するJS。document.getElementById()で対象を
#   直接取得するのみで、document全体へのquerySelectorAll等は一切行わない。
CONTAINER_VISIBLE_CHECK_JS = r"""
(containerId) => {
  const el = document.getElementById(containerId);
  if (!el) return { found: false };
  let visible = false;
  try {
    const r = el.getClientRects();
    visible = r.length > 0 && (el.offsetWidth > 0 || el.offsetHeight > 0);
  } catch (e) {}
  let styleDisplay = null, computedDisplay = null;
  try { styleDisplay = el.style ? el.style.display : null; } catch (e) {}
  try { computedDisplay = window.getComputedStyle(el).display; } catch (e) {}
  return { found: true, visible: visible, tag: el.tagName, id: el.id,
    styleDisplay: styleDisplay, computedDisplay: computedDisplay };
}
"""

# ★CsvdownClose1「内部だけ」に限定してform[name=...]を確認するJS。
#   el.querySelectorAll() はCsvdownClose1のサブツリーにのみ適用される
#   （document全体へのquerySelectorAllは一切行わない）。
FORM_CHECK_JS = r"""
(args) => {
  const el = document.getElementById(args.containerId);
  if (!el) return { containerFound: false };
  const forms = el.querySelectorAll('form[name="' + args.formName + '"]');
  if (forms.length !== 1) {
    return { containerFound: true, formCount: forms.length };
  }
  const f = forms[0];
  return {
    containerFound: true, formCount: 1,
    action: f.getAttribute('action'), method: f.getAttribute('method'), id: f.id || null
  };
}
"""


def _safe_close(context, browser, log):
    """context/browserのクローズ処理を安全に行う。
    どちらかのclose()内でPlaywright側の例外（環境要因等）が発生しても、
    ログに記録するだけで再送出せず、必ず結果txtの保存（_write_result）まで
    到達できるようにするための保険。CSVダウンロード・検証ロジックには影響しない。"""
    try:
        context.close()
    except Exception as e:
        log("[WARN] context.close()中にエラーが発生しました（無視して続行します）: "
            + type(e).__name__ + ": " + str(e)[:300])
    try:
        browser.close()
    except Exception as e:
        log("[WARN] browser.close()中にエラーが発生しました（無視して続行します）: "
            + type(e).__name__ + ": " + str(e)[:300])


def main():
    out_lines = []
    stopped_early = {"flag": False, "reason": ""}
    dialog_state = {"count": 0, "handled": False, "unexpected": False}
    downloads_seen = []
    phase_state = {"expecting_action": False}

    def log(msg=""):
        print(msg)
        out_lines.append(msg)

    def _stop(reason):
        stopped_early["flag"] = True
        stopped_early["reason"] = reason
        log("[STOP] " + reason)

    log("=" * 70)
    log("タスク8 HARU（通常アカウント）CSVダウンロード単体実行テスト")
    log("（★カンマ区切りCSV〈csv01〉を実際に1回だけダウンロードします★）")
    log("実行日時: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    log("=" * 70)
    log("★今回許可されている実操作は、メニュー起点への1回のクリックと、")
    log("　csv01（カンマ区切り）アンカーへの1回のクリックのみです。★")
    log("★csv02（タブ区切り）・problem1〜problem6等、他のformには一切アクセスしません。★")
    log("★CSV→xlsx変換・候補抽出・eBay API・Qty変更・既存タスク8ファイルへの書き込みは")
    log("　一切行いません。★")
    log("★ID/パスワード/Cookie/セッション情報・HTML全文・storage_stateは一切")
    log("　ログ・ファイルに出力しません。★")
    log("")

    # ---- 安全停止条件: ID/PWが空欄ならページを開く前に停止 ----
    if not haru_config.is_configured():
        log("[ERROR] haru_config_tsujou.py の HARU_USER_ID / HARU_PASSWORD が空欄です。")
        log("        ページへのアクセス自体を行わず、ここで安全停止します。")
        _write_result(out_lines)
        return

    log("haru_config_tsujou.py: 設定済みを確認（値そのものは表示しません）")
    log("対象URL: " + haru_config.HARU_LOGIN_URL)
    log("")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # ★今回は実ダウンロードを許可する（accept_downloads=True）★
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # ---- 安全策①: ダウンロードイベントの監視。
        #      「expecting_action=True」の区間で1回だけ発生するもの以外はすべて異常として
        #      キャンセルする（想定外タイミングでの発生・2件目以降のいずれも対象）。----
        def _on_download(download):
            downloads_seen.append(download)
            log("[DOWNLOAD] イベント検出 #" + str(len(downloads_seen))
                + "（suggested_filename=" + str(download.suggested_filename) + "）")
            if (not phase_state["expecting_action"]) or len(downloads_seen) > 1:
                _stop("想定外のタイミング、または複数回のダウンロードイベントを検出しました。"
                      "以後の処理を中断し、このダウンロードはキャンセルします。")
                try:
                    download.cancel()
                except Exception:
                    pass

        # ---- 安全策②: 確認ダイアログの監視。
        #      「expecting_action=True」の区間で発生した1件目・type=confirm・
        #      文言に「カンマ区切り」を含み「タブ区切り」を含まないものだけを受諾する。----
        def _on_dialog(dialog):
            dialog_state["count"] += 1
            # ★2026/08/22修正: Playwright Python Sync APIでは Dialog.message / Dialog.type は
            #   いずれもプロパティ（呼び出し不可）。誤って dialog.message() / dialog.type() と
            #   関数呼び出しをしていたため TypeError: 'str' object is not callable が発生していた。
            msg = dialog.message
            dtype = dialog.type
            log("[DIALOG] 検出 #" + str(dialog_state["count"]) + ": type=" + str(dtype)
                + ", message=" + str(_truncate(msg)))

            ok = (
                phase_state["expecting_action"]
                and dialog_state["count"] == 1
                and dtype == "confirm"
                and (TARGET_DIALOG_MUST_CONTAIN in msg)
                and (TARGET_DIALOG_MUST_NOT_CONTAIN not in msg)
            )
            if ok:
                dialog_state["handled"] = True
                try:
                    dialog.accept()
                    log("         → 想定通りのカンマ区切りCSV確認ダイアログのため受諾しました。")
                except Exception as e:
                    _stop("確認ダイアログの受諾に失敗しました: " + str(e)[:200])
            else:
                dialog_state["unexpected"] = True
                _stop("想定外のタイミング・種別・文言のダイアログを検出しました。受諾しません。")
                try:
                    dialog.dismiss()
                    log("         → dismissしました。")
                except Exception as e:
                    log("[WARN] ダイアログのdismissに失敗しました: " + str(e)[:200])

        # ---- 安全策③: 予期しない新規タブ/ポップアップは開かせず即クローズする ----
        def _on_new_page(new_page):
            _stop("予期しない新規タブ/ポップアップを検出しました。安全のため閉じます。")
            try:
                new_page.close()
            except Exception:
                pass

        page.on("download", _on_download)
        page.on("dialog", _on_dialog)
        context.on("page", _on_new_page)

        # ================= フェーズ1: ログイン（test_haru_login_tsujou.pyと同一処理） =================
        log("-" * 70)
        log("フェーズ1: 通常HARUへログイン")
        log("-" * 70)
        try:
            page.goto(haru_config.HARU_LOGIN_URL, timeout=PAGE_TIMEOUT_MS)
        except Exception as e:
            log("[ERROR] ログインページの読み込みに失敗しました: " + str(e)[:300])
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        try:
            userid_input = page.wait_for_selector("#userid", timeout=10000)
            password_input = page.wait_for_selector("#password", timeout=10000)
            submit_button = page.wait_for_selector("input[type=submit]", timeout=10000)
        except Exception as e:
            log("[ERROR] ログインフォームの要素（#userid / #password / submit）が")
            log("        見つかりませんでした。安全停止します。詳細: " + str(e)[:200])
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        if userid_input is None or password_input is None or submit_button is None:
            log("[ERROR] ログインフォームの要素が取得できませんでした。安全停止します。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        login_url_before = _strip_query(page.url)

        try:
            userid_input.fill(haru_config.HARU_USER_ID)
            password_input.fill(haru_config.HARU_PASSWORD)
            log("ID/パスワードを入力しました（値はログに出力しません）。")
            submit_button.click()
            log("ログインボタンをクリックしました。")
        except Exception as e:
            log("[ERROR] ログインフォームへの入力・送信に失敗しました: " + str(e)[:200])
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        try:
            page.wait_for_load_state("networkidle", timeout=POST_LOGIN_WAIT_MS)
        except Exception:
            log("[WARN] ログイン後のnetworkidle待機がタイムアウトしました。現在の状態で判定を継続します。")

        current_url_stripped = _strip_query(page.url)
        log("")
        log("ログイン前URL（クエリ除去後）: " + login_url_before)
        log("ログイン後URL（クエリ除去後）: " + current_url_stripped)

        url_changed = (current_url_stripped != login_url_before) and ("login" not in current_url_stripped.lower())
        log("判定①（URLがログイン画面から変化）: " + ("OK" if url_changed else "NG"))

        try:
            marker_count = page.get_by_text(TOP_MARKER_TEXT).count()
        except Exception as e:
            marker_count = 0
            log("[WARN] 目印要素の確認中にエラー: " + str(e)[:150])

        marker_found = marker_count > 0
        log("判定②（「" + TOP_MARKER_TEXT + "」テキストの存在。部分一致でカウント）: "
            + ("OK（" + str(marker_count) + "件）" if marker_found else "NG"))

        login_success = url_changed and marker_found

        if not login_success:
            log("")
            _stop("ログインに失敗、または想定と異なる画面と判定しました。"
                  "推測で先へ進まず、安全停止します。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        if stopped_early["flag"]:
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        log("")
        log("★ログイン成功を確認しました。★")
        log("")

        # ================= フェーズ2・3: メニュー起点の特定・1回クリック =================
        log("-" * 70)
        log("フェーズ2: 「" + MENU_TRIGGER_TEXT + "」（完全一致）候補の列挙（★まだクリックしません★）")
        log("-" * 70)

        try:
            trigger_locator = page.get_by_text(MENU_TRIGGER_TEXT, exact=True)
            trigger_count = trigger_locator.count()
        except Exception as e:
            _stop("メニュー起点候補の取得中にエラー: " + str(e)[:200])
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        log("完全一致候補数: " + str(trigger_count))

        visible_candidates = []
        for i in range(trigger_count):
            el = trigger_locator.nth(i)
            try:
                vis = el.is_visible()
            except Exception:
                vis = False
            _describe_element(el, log, "候補" + str(i) + "（visible=" + str(vis) + "）")
            if vis:
                visible_candidates.append(el)

        log("")
        log("可視状態の完全一致候補数: " + str(len(visible_candidates)))

        if len(visible_candidates) != 1:
            log("")
            _stop("「" + MENU_TRIGGER_TEXT + "」の可視候補が1件に絞れませんでした"
                  + "（" + str(len(visible_candidates)) + "件）。推測でクリックせず安全停止します。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        menu_trigger = visible_candidates[0]
        log("")
        log("★メニュー起点を1件に特定しました。★")

        log("-" * 70)
        log("フェーズ3: メニューを開く（1回のクリック）")
        log("-" * 70)

        try:
            menu_trigger.click()
            log("メニュー起点要素をクリックしました。")
        except Exception as e:
            _stop("メニュー起点のクリックに失敗しました: " + str(e)[:200])
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        if stopped_early["flag"]:
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        try:
            page.wait_for_timeout(MENU_OPEN_WAIT_MS)
        except Exception:
            pass

        if stopped_early["flag"]:
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        # ================= フェーズ4: CsvdownClose1 の存在・表示状態確認 =================
        log("-" * 70)
        log("フェーズ4: id=\"" + CSVDOWN_CONTAINER_ID + "\" の存在・表示状態を確認")
        log("-" * 70)

        try:
            visible_result = page.evaluate(CONTAINER_VISIBLE_CHECK_JS, CSVDOWN_CONTAINER_ID)
        except Exception as e:
            _stop(CSVDOWN_CONTAINER_ID + " の状態確認中にエラーが発生しました: " + str(e)[:200])
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        if not visible_result.get("found"):
            _stop("document.getElementById(\"" + CSVDOWN_CONTAINER_ID + "\") が見つかりませんでした。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        log("  tag              : " + str(visible_result.get("tag")))
        log("  id               : " + str(visible_result.get("id")))
        log("  style.display    : " + str(visible_result.get("styleDisplay")))
        log("  computed display : " + str(visible_result.get("computedDisplay")))
        log("  visible相当      : " + str(visible_result.get("visible")))

        if not visible_result.get("visible"):
            _stop(CSVDOWN_CONTAINER_ID + " が表示状態と判定できませんでした。安全停止します。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        log("")
        log("★" + CSVDOWN_CONTAINER_ID + " の表示状態を確認しました。★")

        # ================= フェーズ5: csv01 form の action/method 確認 =================
        log("-" * 70)
        log("フェーズ5: CsvdownClose1内部の form[name=\"" + TARGET_FORM_NAME + "\"] を確認")
        log("-" * 70)

        try:
            form_result = page.evaluate(
                FORM_CHECK_JS, {"containerId": CSVDOWN_CONTAINER_ID, "formName": TARGET_FORM_NAME}
            )
        except Exception as e:
            _stop("csv01 formの確認中にエラーが発生しました: " + str(e)[:200])
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        if not form_result.get("containerFound"):
            _stop(CSVDOWN_CONTAINER_ID + " が見つからなくなりました（想定外）。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        if form_result.get("formCount") != 1:
            _stop("form[name=\"" + TARGET_FORM_NAME + "\"] が1件に特定できませんでした"
                  + "（" + str(form_result.get("formCount")) + "件）。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        form_action = form_result.get("action")
        form_method = (form_result.get("method") or "").upper()
        log("  form action : " + str(form_action))
        log("  form method : " + str(form_method))

        if form_action != TARGET_FORM_ACTION or form_method != TARGET_FORM_METHOD:
            _stop("csv01のaction/methodが想定（" + TARGET_FORM_ACTION + " / " + TARGET_FORM_METHOD
                  + "）と異なります（実際: " + str(form_action) + " / " + str(form_method) + "）。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        log("")
        log("★csv01 formのaction/methodが想定通りであることを確認しました。★")

        # ================= フェーズ6: csv01用アンカーの特定 =================
        log("-" * 70)
        log("フェーズ6: csv01用アンカー（href=\"" + TARGET_HREF + "\"）を特定")
        log("-" * 70)

        try:
            container_locator = page.locator("#" + CSVDOWN_CONTAINER_ID)
            anchor_locator = container_locator.locator('a[href="' + TARGET_HREF + '"]')
            anchor_count = anchor_locator.count()
        except Exception as e:
            _stop("csv01用アンカーの取得中にエラー: " + str(e)[:200])
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        log("該当アンカー数: " + str(anchor_count))

        if anchor_count != 1:
            _stop("csv01用アンカーが1件に特定できませんでした（" + str(anchor_count) + "件）。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        csv01_anchor = anchor_locator.first
        _describe_element(csv01_anchor, log, "csv01アンカー候補")

        try:
            anchor_visible = csv01_anchor.is_visible()
        except Exception:
            anchor_visible = False
        try:
            anchor_onclick = csv01_anchor.get_attribute("onclick") or ""
        except Exception:
            anchor_onclick = ""

        if not anchor_visible:
            _stop("csv01用アンカーが表示状態ではありません。安全停止します。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        if ("confirm(" not in anchor_onclick) or (TARGET_DIALOG_MUST_CONTAIN not in anchor_onclick) \
                or (TARGET_DIALOG_MUST_NOT_CONTAIN in anchor_onclick):
            _stop("csv01用アンカーのonclickが想定（confirm()・「カンマ区切り」を含み"
                  "「タブ区切り」を含まない）と異なります。安全停止します。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        log("")
        log("★csv01用アンカーを1件に特定し、onclickの想定（カンマ区切り確認ダイアログ）を")
        log("　確認しました。次のフェーズでこのアンカーを1回だけクリックします。★")

        # ================= フェーズ7: csv01を1回クリック→確認ダイアログ受諾→ダウンロード待機 =================
        log("-" * 70)
        log("フェーズ7: csv01（カンマ区切り）を1回クリックし、ダウンロードを待機")
        log("-" * 70)
        log("★この区間だけ、確認ダイアログ・ダウンロードイベントの受け入れを許可します。★")

        phase_state["expecting_action"] = True
        download = None
        try:
            try:
                with page.expect_download(timeout=DOWNLOAD_TIMEOUT_MS) as download_info:
                    csv01_anchor.click()
                    log("csv01（カンマ区切り）アンカーをクリックしました。ダウンロードを待機します。")
                download = download_info.value
            except Exception as e:
                if not stopped_early["flag"]:
                    _stop("ダウンロードが既定時間内（" + str(DOWNLOAD_TIMEOUT_MS)
                          + "ms）に完了しませんでした、またはクリック処理でエラーが発生しました: "
                          + type(e).__name__ + ": " + str(e)[:200])
        finally:
            phase_state["expecting_action"] = False

        if stopped_early["flag"] or download is None:
            log("[STOP] ダウンロードを取得できませんでした。ここで安全停止します。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        # ---- ダイアログ・ダウンロードの状態を二重チェック ----
        if not dialog_state["handled"] or dialog_state["count"] != 1 or dialog_state["unexpected"]:
            _stop("確認ダイアログの受諾状態が想定と異なります"
                  "（handled=" + str(dialog_state["handled"]) + ", count=" + str(dialog_state["count"])
                  + ", unexpected=" + str(dialog_state["unexpected"]) + "）。ファイルは保存しません。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        if len(downloads_seen) != 1:
            _stop("ダウンロードイベントの発生回数が想定と異なります（" + str(len(downloads_seen))
                  + "件）。ファイルは保存しません。")
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        try:
            failure = download.failure()
        except Exception:
            failure = None

        if failure:
            _stop("ダウンロードが失敗しました: " + str(failure))
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        log("")
        log("★ダウンロードイベントを1件だけ取得しました。suggested_filename: "
            + str(download.suggested_filename) + "★")

        # ================= フェーズ8: 保存 =================
        log("-" * 70)
        log("フェーズ8: CSVをタスク8フォルダ内のテスト用ファイルへ保存")
        log("-" * 70)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        save_filename = "haru_download_test_tsujou_" + timestamp + ".csv"
        save_path = os.path.join(_THIS_DIR, save_filename)

        if os.path.exists(save_path):
            _stop("保存先ファイルが既に存在するため、上書きせず安全停止します: " + save_filename)
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        try:
            download.save_as(save_path)
        except Exception as e:
            _stop("ダウンロードファイルの保存に失敗しました: " + str(e)[:200])
            _safe_close(context, browser, log)
            _write_result(out_lines)
            return

        log("保存先: " + save_path)

        _safe_close(context, browser, log)

    # ================= フェーズ9: CSV基本検証（読み取り専用） =================
    log("")
    log("-" * 70)
    log("フェーズ9: 保存したCSVの基本検証（読み取り専用・9項目）")
    log("-" * 70)

    ok, _details = _validate_csv(save_path, log)

    log("")
    log("=" * 70)
    if ok:
        log("★判定: ダウンロード成功★（カンマ区切りCSVの取得・基本検証まで完了）")
    else:
        log("★判定: 検証NG★（ダウンロード自体は行われましたが基本検証に失敗したため、")
        log("　「ダウンロード成功」とは扱いません。ファイルは削除せず保持しています。")
        log("　保存先: " + save_path + "）")
    log("=" * 70)

    log("")
    log("★ID/パスワード/Cookie/セッション情報は取得・出力していません。★")
    log("★csv02・problem1〜problem6等、csv01以外のformには一切アクセスしていません。★")
    log("★CSV→xlsx変換・候補抽出・eBay API呼び出し・Qty変更・既存タスク8ファイルへの")
    log("　書き込みは一切行っていません。★")

    _write_result(out_lines)
    log("")
    log("結果を保存しました: " + RESULT_TXT)


def _validate_csv(path, log):
    """保存済みCSVの読み取り専用の基本検証（9項目）。ファイルへの書き込みは一切行わない。"""

    if not os.path.exists(path):
        log("[CSV検証] 1. ファイルの存在: NG（ファイルが見つかりません）")
        return False, {}
    log("[CSV検証] 1. ファイルの存在: OK")

    size = os.path.getsize(path)
    if size <= 0:
        log("[CSV検証] 2. ファイルサイズ: NG（0バイトです）")
        return False, {}
    log("[CSV検証] 2. ファイルサイズ: OK（" + str(size) + " bytes）")

    try:
        with open(path, "r", encoding="cp932", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
    except Exception as e:
        log("[CSV検証] 3. cp932読み取り: NG（" + str(e)[:200] + "）")
        return False, {}
    log("[CSV検証] 3. cp932読み取り: OK（全" + str(len(rows)) + "行）")

    if not rows or not rows[0] or all((c or "").strip() == "" for c in rows[0]):
        log("[CSV検証] 4. ヘッダー行の存在: NG")
        return False, {}
    header = [(c or "").strip() for c in rows[0]]
    log("[CSV検証] 4. ヘッダー行の存在: OK（列数=" + str(len(header)) + "）")
    log("            ヘッダー内容: " + str(header))

    if len(header) != EXPECTED_COLUMN_COUNT:
        log("[CSV検証] 5. 列数: NG（期待=" + str(EXPECTED_COLUMN_COUNT)
            + "、実際=" + str(len(header)) + "）")
        return False, {}
    log("[CSV検証] 5. 列数: OK（" + str(EXPECTED_COLUMN_COUNT) + "列）")

    if EXPECTED_ITEM_COL_NAME not in header:
        log("[CSV検証] 6. 「" + EXPECTED_ITEM_COL_NAME + "」列の存在: NG")
        return False, {}
    item_col_index = header.index(EXPECTED_ITEM_COL_NAME)
    log("[CSV検証] 6. 「" + EXPECTED_ITEM_COL_NAME + "」列の存在: OK（列位置=" + str(item_col_index) + "）")

    if len(header) <= EXPECTED_QTY_COL_INDEX or header[EXPECTED_QTY_COL_INDEX] != EXPECTED_QTY_COL_NAME:
        actual = header[EXPECTED_QTY_COL_INDEX] if len(header) > EXPECTED_QTY_COL_INDEX else "(列なし)"
        log("[CSV検証] 7. " + str(EXPECTED_QTY_COL_INDEX) + "列目(0-indexed)が「"
            + EXPECTED_QTY_COL_NAME + "」: NG（実際=「" + str(actual) + "」）")
        return False, {}
    log("[CSV検証] 7. " + str(EXPECTED_QTY_COL_INDEX) + "列目(0-indexed)が「"
        + EXPECTED_QTY_COL_NAME + "」: OK")

    data_rows = rows[1:]
    if len(data_rows) == 0:
        log("[CSV検証] 8. データ行数: NG（0件）")
        return False, {}
    log("[CSV検証] 8. データ行数: OK（" + str(len(data_rows)) + "件）")

    total = 0
    prefix1 = 0
    for row in data_rows:
        if len(row) <= item_col_index:
            continue
        val = (row[item_col_index] or "").strip()
        if not val:
            continue
        total += 1
        if val[0] == ITEM_ID_NORMAL_PREFIX:
            prefix1 += 1

    if total == 0:
        log("[CSV検証] 9. Item ID先頭判定: NG（Item IDの値が1件も取得できません）")
        return False, {}

    ratio = prefix1 / total
    if ratio <= ITEM_ID_MAJORITY_RATIO:
        log("[CSV検証] 9. Item ID先頭判定: NG（先頭が「" + ITEM_ID_NORMAL_PREFIX + "」の件数="
            + str(prefix1) + "/" + str(total) + "、通常アカウント用CSVと判断できません）")
        return False, {}
    log("[CSV検証] 9. Item ID先頭判定: OK（先頭が「" + ITEM_ID_NORMAL_PREFIX + "」の件数="
        + str(prefix1) + "/" + str(total) + "、通常アカウント用CSVと判断）")

    return True, {"header": header, "item_col_index": item_col_index, "data_rows": len(data_rows)}


def _write_result(lines):
    try:
        with open(RESULT_TXT, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        print("[WARN] 結果ファイルの保存に失敗しました: " + str(e))


if __name__ == "__main__":
    main()
