#!/usr/bin/env python3
"""
从 kana-data.json 随机选择3个未学假名
输出格式：每行 "hira|kata|roma|mnemonic"
"""
import json
import random
import sys
import os

WORKSPACE = os.path.expanduser("~/.openclaw/workspace/japanese-learning")
progress_file = os.path.join(WORKSPACE, "progress.json")
kana_file = os.path.join(WORKSPACE, "kana-data.json")

try:
    # 1. 读取已掌握列表
    with open(progress_file, "r", encoding="utf-8") as f:
        progress = json.load(f)
    mastered = set(progress.get("mastered", []))

    # 2. 读取所有假名
    with open(kana_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 3. 收集未掌握的假名
    available = []
    for row in data["rows"]:
        for k in row["kana"]:
            if k["hiragana"] not in mastered:
                available.append(k)

    if not available:
        print("ALL_DONE")
        sys.exit(0)

    # 4. 随机选3个
    random.shuffle(available)
    selected = available[:3]

    # 5. 输出
    for k in selected:
        print(f"{k['hiragana']}|{k['katakana']}|{k['romaji']}|{k['mnemonic']}")

except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
