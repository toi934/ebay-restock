# -*- coding: utf-8 -*-
"""HARU（通常アカウント）ログイン情報 - GitHub Actions版

ローカル版(ﾀｽｸ8_eBay Qty 0→1（HARU在庫復活）\\haru_config_tsujou.py)との違い:
  HARU_USER_ID / HARU_PASSWORD をハードコードせず、GitHub Secrets
  (HARU_USER_ID / HARU_PASSWORD) から環境変数経由で読み込む。
  is_configured() のインターフェースはローカル版と同一。
"""
import os

HARU_USER_ID = os.environ.get("HARU_USER_ID", "")
HARU_PASSWORD = os.environ.get("HARU_PASSWORD", "")

# HARU（通常アカウント）のログインページ（秘密情報ではないためハードコード）
HARU_LOGIN_URL = "https://haru-tk2-242-30542.work/new_haru/"


def is_configured():
    return bool(HARU_USER_ID.strip()) and bool(HARU_PASSWORD.strip())


if __name__ == "__main__":
    if is_configured():
        print("OK: ログイン情報が設定されています（環境変数から読込）")
    else:
        print("ERROR: HARU_USER_ID / HARU_PASSWORD の環境変数（GitHub Secrets）が未設定です")
