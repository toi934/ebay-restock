from pathlib import Path
import csv, re
from datetime import datetime
from openpyxl import Workbook, load_workbook

BASE = Path(__file__).resolve().parent
EXPECTED_COLS = 20
ITEM_HEADER = "eBay Item Number"
QTY_HEADER = "eBay Qty"
QTY_INDEX = 18
NUMERIC_HEADERS = {"仕入価格","*仕入価格-マッチ(1 or 0)","仕入送料","*在庫ワード-マッチ(1 or 0)","*Watchモード(ON:1 or OFF:0)","eBay送料","期待利益","手数料係数","eBay価格","*チェック","*eBay自動連携機能(ON:1 or OFF:0)","eBay Qty","*Watchモード在庫なし判定(ON:1 or OFF:0)"}

def stop(msg):
    print("[STOP] " + msg)
    raise SystemExit(1)

def select_latest():
    rx=re.compile(r"^haru_download_test_tsujou_(\d{8}_\d{6})\.csv$")
    found=[]
    for p in BASE.glob("haru_download_test_tsujou_*.csv"):
        m=rx.match(p.name)
        if m:
            found.append((datetime.strptime(m.group(1),"%Y%m%d_%H%M%S"),m.group(1),p))
    if not found: stop("規定名の入力CSVがありません。")
    newest=max(x[0] for x in found)
    hits=[x for x in found if x[0]==newest]
    if len(hits)!=1: stop("最新時刻のCSVを一意に決定できません。")
    return hits[0][2],hits[0][1]

def read_input(path):
    try:
        with path.open("r",encoding="cp932",newline="") as f: rows=list(csv.reader(f))
    except Exception as e: stop(f"cp932読み取り失敗: {type(e).__name__}: {e}")
    if not rows: stop("CSVが空です。")
    h,d=rows[0],rows[1:]
    if len(h)!=20: stop(f"ヘッダー列数NG: {len(h)}")
    if ITEM_HEADER not in h: stop("eBay Item Number列なし。")
    if h[QTY_INDEX]!=QTY_HEADER: stop("18列目(0-indexed)がeBay Qtyではありません。")
    if not d: stop("データ行0件。")
    for n,r in enumerate(d,2):
        if len(r)!=20: stop(f"{n}行目の列数NG: {len(r)}")
    return h,d

def item_id(s,rowno):
    s=s.strip()
    if not s or not s.isdigit(): stop(f"{rowno}行目 Item ID不正: {s!r}")
    return int(s)  # floatを経由しない

def numeric(s):
    raw=s.strip()
    if raw=="": return ""
    t=raw.replace(",","")
    if re.fullmatch(r"[+-]?\d+",t): return int(t)
    if re.fullmatch(r"[+-]?(?:\d+\.\d*|\d*\.\d+)",t): return float(t)
    return raw

def main():
    src,stamp=select_latest()
    h,d=read_input(src)
    ii=h.index(ITEM_HEADER)
    ids=[item_id(r[ii],n) for n,r in enumerate(d,2)]
    p1=sum(str(x).startswith("1") for x in ids); p3=sum(str(x).startswith("3") for x in ids)
    if p1<=len(ids)/2: stop("Item ID先頭1が過半数ではありません。")
    if p3>len(ids)/2: stop("Item ID先頭3が過半数です。")
    out=BASE/f"{stamp}_通常.xlsx"
    if out.exists(): stop(f"既存xlsxを上書きしません: {out.name}")
    ni={i for i,x in enumerate(h) if x in NUMERIC_HEADERS}
    wb=Workbook(); ws=wb.active; ws.title="HARU"; ws.append(h)
    for n,r in enumerate(d,2):
        ws.append([item_id(v,n) if i==ii else numeric(v) if i in ni else v for i,v in enumerate(r)])
    for row in range(2,ws.max_row+1): ws.cell(row,ii+1).number_format="0"
    wb.save(out)
    chk=load_workbook(out,read_only=True,data_only=False); s=chk["HARU"]
    ok_shape=(s.max_column==20 and s.max_row-1==len(d) and s.cell(1,QTY_INDEX+1).value==QTY_HEADER)
    ok_item=True; ok_qty=True
    if ok_shape:
        # ★2026/08/25修正: s.cell()による全行ランダムアクセス（低速・既知のopenpyxl
        # 落とし穴）を廃止し、iter_rows()による1回の順次読み取りでItem IDとeBay Qtyを
        # 同時検証する。判定条件（4,501行・Item ID全行一致・eBay Qty全行一致）は無変更。
        for n,(r,xr) in enumerate(zip(d,s.iter_rows(min_row=2,values_only=True)),2):
            if xr[ii]!=item_id(r[ii],n): ok_item=False
            if xr[QTY_INDEX]!=numeric(r[QTY_INDEX]): ok_qty=False
    else:
        ok_item=False; ok_qty=False
    chk.close()
    if not (ok_shape and ok_item and ok_qty):
        try: out.unlink()
        except Exception: pass
        stop("変換後全行検証NG。成功ファイルは残しません。")
    print("使用CSVファイル名:",src.name)
    print("CSVデータ行数:",len(d))
    print("xlsx保存ファイル名:",out.name)
    print("xlsxデータ行数:",len(d))
    print("列数: 20")
    print("eBay Item Number全行一致結果: OK")
    print("eBay Qty全行一致結果: OK")
    print("S列ヘッダー確認結果: OK")
    print("Item ID先頭1件数:",p1)
    print("Item ID先頭3件数:",p3)
    print("型変換した列一覧:",[h[i] for i in sorted(ni)])
    print("変換エラー件数: 0")
    print("最終判定: OK")

if __name__=="__main__":
    main()
