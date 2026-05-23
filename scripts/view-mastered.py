#!/usr/bin/env python3
"""
日语五十音复习脚本（增强版）
显示已掌握的假名，助记词也标注罗马音
"""
import json
import sys
import random
from pathlib import Path

def load_json(path):
    """加载 JSON 文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"错误：文件格式不正确 {path}", file=sys.stderr)
        sys.exit(1)

def add_romaji_to_mnemonic(mnemonic, romaji):
    """
    给助记词加上罗马音标注
    例如：ひと（人） + hi → ひと（ひと=人, hito）
    """
    # 提取假名部分（括号前）
    import re
    match = re.match(r'([ぁ-んァ-ヶー]+)（([^）]+)）', mnemonic)
    if match:
        kana = match.group(1)
        meaning = match.group(2)
        return f"{kana}（{kana}={meaning}, {romaji}{meaning}）"
    return f"{mnemonic} ({romaji})"

def main():
    workspace = Path.home() / ".openclaw" / "workspace"
    kana_data_path = workspace / "japanese-learning" / "kana-data.json"
    progress_path = workspace / "japanese-learning" / "progress.json"
    
    # 加载数据
    kana_data = load_json(kana_data_path)
    progress = load_json(progress_path)
    
    # 获取已掌握的假名
    mastered_hiragana = set(progress.get("mastered", []))
    
    if not mastered_hiragana:
        print("📖 还没有掌握任何假名，先去学习吧！")
        print("💡 提示：等待日语学习推送，或者查看日语学习 Skill")
        return
    
    # 解析命令行参数
    mode = sys.argv[1] if len(sys.argv) > 1 else "list"
    filter_row = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 构建假名信息字典
    kana_info = {}
    for row_data in kana_data["rows"]:
        row_name = row_data["row"]
        for kana in row_data["kana"]:
            hira = kana["hiragana"]
            kana_info[hira] = {
                "katakana": kana["katakana"],
                "romaji": kana["romaji"],
                "mnemonic": kana["mnemonic"],
                "row": row_name
            }
    
    # 筛选已掌握的假名
    mastered_list = []
    for hira in mastered_hiragana:
        if hira in kana_info:
            info = kana_info[hira].copy()
            info["hiragana"] = hira
            if filter_row is None or info["row"] == filter_row:
                mastered_list.append(info)
    
    if not mastered_list:
        if filter_row:
            print(f"📖 在 {filter_row} 中还没有掌握任何假名")
        else:
            print("📖 还没有掌握任何假名")
        return
    
    # 按行分组
    by_row = {}
    for item in mastered_list:
        row = item["row"]
        if row not in by_row:
            by_row[row] = []
        by_row[row].append(item)
    
    if mode == "list":
        # 列表模式：显示所有已掌握的假名
        print(f"📖 已掌握的假名（共 {len(mastered_list)} 个）\n")
        for row_name in sorted(by_row.keys()):
            items = by_row[row_name]
            print(f"【{row_name}】")
            for item in items:
                enhanced_mnemonic = add_romaji_to_mnemonic(item['mnemonic'], item['romaji'])
                print(f"  {item['hiragana']} ({item['katakana']}) → {item['romaji']}  {enhanced_mnemonic}")
            print()
    
    elif mode == "quiz":
        # 测验模式：随机抽查
        print(f"📝 五十音复习测验（已掌握 {len(mastered_list)} 个）\n")
        random.shuffle(mastered_list)
        
        # 显示假名，让用户回忆
        for i, item in enumerate(mastered_list[:10], 1):  # 最多显示10个
            print(f"Q{i}: {item['hiragana']} ({item['katakana']})")
            print(f"   回忆：罗马音 = ?  助记 = ?\n")
        
        print("💡 答案：")
        for i, item in enumerate(mastered_list[:10], 1):
            enhanced_mnemonic = add_romaji_to_mnemonic(item['mnemonic'], item['romaji'])
            print(f"A{i}: {item['romaji']} - {enhanced_mnemonic}")
        
        if len(mastered_list) > 10:
            print(f"\n... 还有 {len(mastered_list) - 10} 个未显示")
    
    elif mode == "random":
        # 随机显示一个
        item = random.choice(mastered_list)
        enhanced_mnemonic = add_romaji_to_mnemonic(item['mnemonic'], item['romaji'])
        print(f"🎲 随机复习：{item['hiragana']} ({item['katakana']})")
        print(f"   罗马音：{item['romaji']}")
        print(f"   助记：{enhanced_mnemonic}")
        print(f"   所属：{item['row']}")
        # 同时显示片假名对照
        print(f"\n💡 提示：片假名是 {item['katakana']}，读作 {item['romaji']}")
    
    else:
        print(f"错误：未知模式 '{mode}'", file=sys.stderr)
        print("支持的模式：list, quiz, random", file=sys.stderr)
        sys.exit(1)
    
    # 显示统计信息
    print(f"\n📊 统计：")
    print(f"   总掌握：{progress.get('masteredCount', len(mastered_hiragana))} 个")
    print(f"   准确率：{progress.get('accuracyRate', 'N/A')}%")
    print(f"   已掌握行：{', '.join(sorted(by_row.keys()))}")

if __name__ == "__main__":
    main()
