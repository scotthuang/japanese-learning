#!/usr/bin/env python3
"""
迁移脚本：将旧格式的 daily/*.json 文件迁移到新的多窗口格式。
旧数据整体放入 morning 窗口。

用法：
  python3 migrate-daily.py              # 迁移所有旧格式文件
  python3 migrate-daily.py --dry-run    # 仅预览，不实际修改
  python3 migrate-daily.py --file 2026-06-09.json  # 迁移指定文件
"""

import json
import os
import sys
import glob
import argparse
from datetime import datetime

DAILY_DIR = os.path.expanduser("~/.openclaw/workspace/japanese-learning/daily")
BACKUP_DIR = os.path.join(DAILY_DIR, ".migration_backup")


def is_old_format(data):
    """检查是否为旧格式（没有 windows 字段）"""
    return "windows" not in data


def migrate_file(filepath, dry_run=False):
    """迁移单个文件到新格式"""
    filename = os.path.basename(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not is_old_format(data):
        return False, "已为新格式，跳过"

    # 创建备份
    if not dry_run:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_path = os.path.join(BACKUP_DIR, filename)
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # 构建新格式
    new_data = {
        "date": data.get("date", filename.replace(".json", "")),
        "dayNumber": data.get("dayNumber", 0),
        "kanaLearned": data.get("kanaLearned", []),
        "windows": {
            "morning": {
                "pushed": data.get("pushed", False),
                "pushedAt": data.get("pushedAt"),
                "questions": data.get("questions", []),
                "userReply": data.get("userReply"),
                "questionResults": data.get("questionResults", []),
                "correctCount": data.get("correctCount", 0),
                "accuracy": data.get("accuracy", 0),
                "replied": data.get("replied", False),
                "repliedAt": data.get("repliedAt"),
            },
            "afternoon": {
                "pushed": False,
                "pushedAt": None,
                "questions": [],
                "userReply": None,
                "questionResults": [],
                "correctCount": 0,
                "accuracy": 0,
                "replied": False,
                "repliedAt": None,
            },
            "evening": {
                "pushed": False,
                "pushedAt": None,
                "questions": [],
                "userReply": None,
                "questionResults": [],
                "correctCount": 0,
                "accuracy": 0,
                "replied": False,
                "repliedAt": None,
            },
        },
        "allWindowsPushed": False,
        "totalCorrectCount": data.get("correctCount", 0),
        "totalAccuracy": data.get("accuracy", 0),
    }

    # 保留额外字段（如 _answeredOn, _originalDate）
    for key in data:
        if key.startswith("_") and key not in new_data:
            new_data[key] = data[key]

    if not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)

    return True, "已迁移"


def main():
    parser = argparse.ArgumentParser(description="迁移 daily JSON 文件到多窗口格式")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际修改")
    parser.add_argument("--file", help="迁移指定文件（仅文件名，如 2026-06-09.json）")
    args = parser.parse_args()

    dry_run = args.dry_run

    if args.file:
        filepath = os.path.join(DAILY_DIR, args.file)
        if not os.path.isfile(filepath):
            print(f"❌ 文件不存在: {filepath}")
            sys.exit(1)
        files = [filepath]
    else:
        files = sorted(glob.glob(os.path.join(DAILY_DIR, "*.json")))

    if not files:
        print("没有找到 daily JSON 文件")
        sys.exit(0)

    migrated = 0
    skipped = 0

    for filepath in files:
        filename = os.path.basename(filepath)
        success, msg = migrate_file(filepath, dry_run=dry_run)
        if success:
            print(f"✅ {filename} — {msg}")
            migrated += 1
        else:
            print(f"⏭️  {filename} — {msg}")
            skipped += 1

    print(f"\n📊 迁移完成: {migrated} 个文件已迁移, {skipped} 个跳过")
    if dry_run:
        print("💡 这是预览模式，文件未被修改。去掉 --dry-run 可实际执行。")
    elif migrated > 0:
        print(f"💾 备份已保存到: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
