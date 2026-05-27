#!/usr/bin/env python3
"""
五十音图查询脚本
读取 kana-data.json，生成 Markdown 表格输出
只显示清音（不显示浊音、半浊音、拗音）
"""

import json
import os
import sys

def main():
    # 查找 kana-data.json
    # 默认路径
    default_path = os.path.expanduser("~/.openclaw/workspace/japanese-learning/kana-data.json")

    # 或从配置文件读取
    config_file = os.path.expanduser("~/.openclaw/workspace/configs/japanese-learning.json")
    kana_data_file = default_path

    if os.path.isfile(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                kana_data_file = os.path.expanduser(config["workspace"]["kana_data"])
        except Exception:
            pass

    # 读取假名数据
    try:
        with open(kana_data_file, "r", encoding="utf-8") as f:
            kana_data = json.load(f)
    except Exception as e:
        print(f"❌ 读取假名数据失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 生成 Markdown 表格
    lines = []
    lines.append("## 五十音图（清音）")
    lines.append("")
    lines.append("| 行 | 平假名 (罗马音) | 片假名 (罗马音) | 平假名 (罗马音) | 片假名 (罗马音) | 平假名 (罗马音) | 片假名 (罗马音) | 平假名 (罗马音) | 片假名 (罗马音) | 平假名 (罗马音) | 片假名 (罗马音) |")
    lines.append("|----|----|----|----|----|----|----|----|----|----|")

    for row in kana_data["rows"]:
        row_name = row["row"]
        kana_list = row["kana"]

        cells = [row_name]
        for k in kana_list:
            hira = f"{k['hiragana']} ({k['romaji']})"
            kata = f"{k['katakana']} ({k['romaji']})"
            cells.append(hira)
            cells.append(kata)

        # 如果某行假名不足5个（如や行、わ行），用空单元格补齐
        while len(cells) < 11:  # 1 (行名) + 5 * 2 (平+片)
            cells.append("")

        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
