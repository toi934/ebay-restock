# -*- coding: utf-8 -*-
"""
タスク1（通常）HARU在庫あり判定 - 最小構成モジュール（DRAFT・未適用）
作成: 2026/08/29（戸井さん承認の統合方針に基づく検証用ドラフト）

タスク8 check_candidates.py の find_haru_files_for_account("tsujou") /
get_haru_s_qty() のロジックを、通常アカウント専用に最小構成で移植したもの。
専門(senmon)関連のコード・判定は一切含まない（「専門版は変更しない」の指示に基づく。
このファイルはタスク1通常専用のGitHub Actionsフォルダ内にのみ置く想定で、
タスク8側のファイル・専門側のファイルは一切参照・変更しない）。

★HARU在庫判定ルール（2026/08/09戸井さん確定・絶対厳守）★
  S列（0-indexed 18列目、ヘッダー名"eBay Qty"）が「整数の1」である行のみ「在庫あり」とする。
  J列（在庫ワード-マッチ、0-indexed 9列目）は一切参照しない。
  S列が1以外（0、空欄、文字列、読み取り不能等）の商品はすべて「在庫あり」とは判定しない
  （＝更新禁止側に倒す。安全側の設計）。
"""
import os
import re
import glob
import openpyxl

SUFFIX_RE = re.compile(r"^(\d{8}_\d{6})_通常\.xlsx$")
LEGACY_RE = re.compile(r"^(\d{8}_\d{6})\.xlsx$")
ITEM_ID_COL = 2   # 0-indexed: eBay Item Number
S_QTY_COL = 18    # 0-indexed: eBay Qty（HARU側スナップショット値）


class HaruTsujouFileNotFoundError(RuntimeError):
    """通常アカウント向けのHARUファイルを安全に一意特定できない場合に送出する。
    ★安全側の設計: 該当ファイルが無い・一意に決まらない・中身と矛盾する場合は
      フォールバックで妥協せず、呼び出し元で処理全体を停止させる。★"""
    pass


def _check_tsujou_dominance(path):
    """1ファイルについて、Item Number列(0-indexed 2列目)が有効な行のうち、
    先頭が'1'（通常アカウント）の行の割合が過半数(50%超)かどうかを判定する。
    タスク8 check_candidates._check_account_dominance と同一ロジック（通常専用に固定）。
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    total_valid = 0
    tsujou_rows = 0
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r is None or len(r) < 19:
            continue
        item_no = r[ITEM_ID_COL]
        if item_no in (None, "", 0):
            continue
        total_valid += 1
        if str(item_no).strip().startswith("1"):
            tsujou_rows += 1
    wb.close()
    ratio = (tsujou_rows / total_valid) if total_valid > 0 else 0.0
    return {
        "path": path, "tsujou_rows": tsujou_rows, "total_valid_rows": total_valid,
        "ratio": ratio, "is_dominant": total_valid > 0 and ratio > 0.5,
    }


def find_latest_haru_file_tsujou(directory):
    """通常アカウント向け最新HARUファイルを1つ選ぶ（tsujou専用・読み取り専用）。

    判定順序（check_candidates.find_haru_files_for_account と同じ考え方。
    通常アカウント以外の分岐は持たない）:
      1. "YYYYMMDD_HHMMSS_通常.xlsx" 形式を最優先。複数あれば最新スタンプを採用。
         同一スタンプで複数存在し一意に決まらない場合は安全停止する。
      2. 該当ファイルが1件も無い場合のみ、旧形式 "YYYYMMDD_HHMMSS.xlsx" の中から
         新しい順に、Item ID先頭'1'が過半数(50%超)のファイルを探す。
      3. どちらも無ければ安全停止する。

    戻り値: (path, info)
      info = {"source": "suffixed(_通常)" / "legacy_fallback",
              "tsujou_rows", "total_valid_rows", "ratio", "is_dominant"}
    """
    suffixed = []
    for f in glob.glob(os.path.join(directory, "*.xlsx")):
        bn = os.path.basename(f)
        if bn.startswith("~$"):
            continue
        m = SUFFIX_RE.match(bn)
        if m:
            suffixed.append((m.group(1), f))

    if suffixed:
        suffixed.sort(key=lambda t: t[0], reverse=True)
        newest_stamp = suffixed[0][0]
        same_stamp_files = [p for s, p in suffixed if s == newest_stamp]
        if len(same_stamp_files) != 1:
            raise HaruTsujouFileNotFoundError(
                "通常アカウント向けHARUファイルが同一日時(" + newest_stamp
                + ")で複数存在し、一意に決定できません（安全停止）: "
                + ", ".join(os.path.basename(p) for p in same_stamp_files))
        path = same_stamp_files[0]
        check = _check_tsujou_dominance(path)
        if not check["is_dominant"]:
            raise HaruTsujouFileNotFoundError(
                "通常アカウント向けファイル " + os.path.basename(path)
                + " ですが、中身のItem ID先頭'1'が過半数ではありません（"
                + str(check["tsujou_rows"]) + "/" + str(check["total_valid_rows"])
                + "）。ファイル名と中身が矛盾するため安全停止します。")
        info = dict(check)
        info["source"] = "suffixed(_通常)"
        return path, info

    legacy = []
    for f in glob.glob(os.path.join(directory, "*.xlsx")):
        bn = os.path.basename(f)
        if bn.startswith("~$"):
            continue
        if LEGACY_RE.match(bn):
            legacy.append(f)
    legacy.sort(key=lambda p: os.path.basename(p), reverse=True)

    checked = []
    for path in legacy:
        check = _check_tsujou_dominance(path)
        checked.append(check)
        if check["is_dominant"]:
            info = dict(check)
            info["source"] = "legacy_fallback"
            return path, info

    detail = "; ".join(
        os.path.basename(c["path"]) + "(先頭'1': " + str(c["tsujou_rows"])
        + "/" + str(c["total_valid_rows"]) + ")"
        for c in checked
    )
    raise HaruTsujouFileNotFoundError(
        "通常アカウント向けのHARUファイルが見つかりません（" + directory
        + " 内に _通常.xlsx 形式・旧形式とも該当なし。旧形式の確認内訳: " + detail + "）。")


def load_haru_s1_item_ids(path):
    """HARUファイルからS列(eBay Qty、0-indexed18列目)が「整数の1」の行のみを対象に、
    Item IDの集合を返す（Item IDは文字列化。eBay GetMyeBaySellingが返すItemID文字列と
    そのまま比較できる形式にする）。

    S列が1以外（0・空欄・非数値・文字列・読み取り不能等）の行は一切含まれない。
    J列（在庫ワード-マッチ）は参照しない。

    戻り値: (s1_item_ids: set[str], total_rows: int)
    """
    ext = os.path.splitext(path)[1].lower()
    if ext != ".xlsx":
        raise RuntimeError("未対応の拡張子です（.xlsxのみ対応）: " + path)

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()

    s1_ids = set()
    for r in rows:
        if r is None or len(r) < 19:
            continue
        item_no = r[ITEM_ID_COL]
        if item_no in (None, "", 0):
            continue
        s_qty = r[S_QTY_COL]
        if s_qty == 1:  # ★厳密な整数1との一致のみ。0/空欄/文字列/その他はすべて対象外★
            s1_ids.add(str(item_no))
    return s1_ids, len(rows)
