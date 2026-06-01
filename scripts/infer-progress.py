#!/usr/bin/env python3
"""
日语学习进度推理脚本（增强版）
- 分析每日答题详情，统计每个假名的掌握度
- 生成/更新 learning-profile.md（个人学习档案）
- 输出第二天学习方案，供推送脚本读取
读取配置文件：~/.openclaw/workspace/configs/japanese-learning.json
"""

import json
import os
import sys
import glob
import re
from datetime import datetime
from collections import defaultdict

# 配置文件路径
CONFIG_FILE = os.path.expanduser("~/.openclaw/workspace/configs/japanese-learning.json")

def load_config():
    """从配置文件读取配置"""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}", file=sys.stderr)
        return None

def load_json(path):
    """读取 JSON 文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 读取 {path} 失败: {e}", file=sys.stderr)
        return None

def save_json(path, data):
    """保存 JSON 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_all_kana(config):
    """从 kana-data.json 读取所有假名"""
    kana_data_file = os.path.expanduser(config["workspace"]["kana_data"])
    with open(kana_data_file, "r", encoding="utf-8") as f:
        kana_data = json.load(f)
    
    all_kana = {}
    for row in kana_data["rows"]:
        for k in row["kana"]:
            all_kana[k["hiragana"]] = {
                "hiragana": k["hiragana"],
                "katakana": k["katakana"],
                "romaji": k["romaji"],
                "mnemonic": k.get("mnemonic", ""),
                "row": row["row"]
            }
    return all_kana

def analyze_daily_records(daily_dir, all_kana):
    """
    分析所有每日档案，统计每个假名的答题情况
    返回：kana_stats = {假名: {attempts, correct, accuracy, last_seen}}
    """
    kana_stats = defaultdict(lambda: {"attempts": 0, "correct": 0, "accuracy": 0.0, "last_seen": None, "row": None})
    
    # 初始化所有假名
    for hira, info in all_kana.items():
        kana_stats[hira]["row"] = info["row"]
    
    daily_files = sorted(glob.glob(os.path.join(daily_dir, "*.json")))
    
    for fpath in daily_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                daily = json.load(f)
        except Exception:
            continue
        
        date = daily.get("date", "?")
        results = daily.get("questionResults", [])
        
        for q in results:
            kana = q.get("kana")
            if not kana or kana not in all_kana:
                continue
            
            kana_stats[kana]["attempts"] += 1
            if q.get("isCorrect"):
                kana_stats[kana]["correct"] += 1
            if not kana_stats[kana]["last_seen"] or date > kana_stats[kana]["last_seen"]:
                kana_stats[kana]["last_seen"] = date
    
    # 计算正确率
    for kana, stats in kana_stats.items():
        if stats["attempts"] > 0:
            stats["accuracy"] = round(stats["correct"] / stats["attempts"] * 100, 2)
        else:
            stats["accuracy"] = None  # 未考过
    
    return kana_stats

def generate_learning_profile(progress, kana_stats, all_kana, daily_dir):
    """生成 learning-profile.md"""
    mastered = set(progress.get("mastered", []))
    mastered_count = len(mastered)
    total_kana = 46
    accuracy_rate = progress.get("accuracyRate", 0)
    trend = progress.get("trend", "stable")
    
    # 统计各行
    row_stats = defaultdict(lambda: {"total": 0, "mastered": 0, "accuracy": 0.0, "kana_list": []})
    
    for hira, info in all_kana.items():
        row = info["row"]
        row_stats[row]["total"] += 1
        row_stats[row]["kana_list"].append(info)
        
        if hira in mastered:
            row_stats[row]["mastered"] += 1
        
        # 计算该行的平均正确率（只算考过的）
        kana_in_row = [k for k in row_stats[row]["kana_list"]]
        accuracies = [kana_stats[k["hiragana"]]["accuracy"] for k in kana_in_row if kana_stats[k["hiragana"]]["accuracy"] is not None]
        if accuracies:
            row_stats[row]["accuracy"] = round(sum(accuracies) / len(accuracies), 2)
    
    # 找出已掌握、易错、未学的假名
    mastered_kana = []
    error_prone = []
    not_learned = []
    
    for hira, stats in kana_stats.items():
        if stats["accuracy"] is None:
            not_learned.append(hira)
        elif stats["accuracy"] >= 80:
            mastered_kana.append((hira, stats))
        elif stats["accuracy"] < 60:
            error_prone.append((hira, stats))
    
    # 排序：按正确率从低到高
    error_prone.sort(key=lambda x: x[1]["accuracy"])
    
    # 生成第二天的学习方案
    tomorrow = (datetime.now().date()).strftime("%Y-%m-%d")
    
    # 新学：从 あ行开始，选未学的行
    new_rows = []
    for row_name in ["あ行", "か行", "さ行", "た行", "な行", "は行", "ま行", "や行", "ら行", "わ行"]:
        if row_stats[row_name]["mastered"] < row_stats[row_name]["total"]:
            new_rows.append(row_name)
            if len(new_rows) >= 1:  # 推荐 1 行
                break
    
    # 巩固：从易错假名中选
    review_kana = [hira for hira, _ in error_prone[:5]]  # 最多 5 个
    
    # 生成 Markdown
    lines = [
        "# 日语五十音学习档案",
        "",
        f"> 最后更新：{datetime.now():%Y-%m-%d %H:%M}",
        "",
        "## 📊 总体情况",
        "",
        "| 项目 | 数值 |",
        "|------|------|",
        f"| 已学天数 | {len(progress.get('dailyRecords', []))} 天 |",
        f"| 已掌握假名 | {mastered_count} / {total_kana} |",
        f"| 总体正确率 | {accuracy_rate}% |",
        f"| 学习趋势 | {trend} |",
        "",
        "### 掌握度分布",
        "",
        "| 行 | 总数 | 已掌握 | 正确率 | 状态 |",
        "|----|------|--------|--------|------|",
    ]
    
    for row_name in ["あ行", "か行", "さ行", "た行", "な行", "は行", "ま行", "や行", "ら行", "わ行"]:
        stats = row_stats[row_name]
        status = "✅ 已掌握" if stats["mastered"] == stats["total"] else \
                "⚠️ 学习中" if stats["mastered"] > 0 else "❌ 未学"
        lines.append(f"| {row_name} | {stats['total']} | {stats['mastered']} | {stats['accuracy']}% | {status} |")
    
    lines.extend([
        "",
        "## 🎯 假名掌握详情",
        "",
        "### ✅ 已掌握（正确率 ≥ 80%）",
        "",
    ])
    
    if mastered_kana:
        lines.append("| 假名 | 片假名 | 读音 | 答题次数 | 正确率 |")
        lines.append("|------|--------|------|----------|--------|")
        for hira, stats in mastered_kana:
            info = all_kana[hira]
            lines.append(f"| {hira} | {info['katakana']} | {info['romaji']} | {stats['attempts']} | {stats['accuracy']}% |")
    else:
        lines.append("（暂无）")
    
    lines.extend([
        "",
        "### ⚠️ 易错假名（正确率 < 60%）",
        ""
    ])
    
    if error_prone:
        lines.append("| 假名 | 片假名 | 读音 | 答题次数 | 正确率 |")
        lines.append("|------|--------|------|----------|--------|")
        for hira, stats in error_prone:
            info = all_kana[hira]
            lines.append(f"| {hira} | {info['katakana']} | {info['romaji']} | {stats['attempts']} | {stats['accuracy']}% |")
    else:
        lines.append("（暂无）")
    
    lines.extend([
        "",
        "### 📝 各假名统计",
        "",
        "| 假名 | 片假名 | 读音 | 答题次数 | 正确次数 | 正确率 | 状态 |",
        "|------|--------|------|----------|----------|--------|------|",
    ])
    
    for hira, stats in sorted(kana_stats.items(), key=lambda x: x[0]):
        info = all_kana.get(hira, {})
        if stats["accuracy"] is None:
            lines.append(f"| {hira} | {info.get('katakana', '?')} | {info.get('romaji', '?')} | 0 | 0 | 未考 | - |")
        elif stats["accuracy"] >= 80:
            lines.append(f"| {hira} | {info.get('katakana', '?')} | {info.get('romaji', '?')} | {stats['attempts']} | {stats['correct']} | {stats['accuracy']}% | ✅ |")
        elif stats["accuracy"] < 60:
            lines.append(f"| {hira} | {info.get('katakana', '?')} | {info.get('romaji', '?')} | {stats['attempts']} | {stats['correct']} | {stats['accuracy']}% | ⚠️ |")
        else:
            lines.append(f"| {hira} | {info.get('katakana', '?')} | {info.get('romaji', '?')} | {stats['attempts']} | {stats['correct']} | {stats['accuracy']}% | 📖 |")
    
    lines.extend([
        "",
        "## 📅 学习历史",
        "",
        "| 日期 | 天数 | 学习假名 | 正确率 | 新学 | 复习 |",
        "|------|------|----------|--------|------|------|",
    ])
    
    daily_files = sorted(glob.glob(os.path.join(daily_dir, "*.json")))
    for fpath in daily_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                daily = json.load(f)
            date = daily.get("date", "?")
            day_num = daily.get("dayNumber", "?")
            kana_learned = " ".join(daily.get("kanaLearned", []))
            accuracy = daily.get("accuracy", 0)
            new_count = len([q for q in daily.get("questionResults", []) if not q.get("isReview")])
            review_count = len([q for q in daily.get("questionResults", []) if q.get("isReview")])
            lines.append(f"| {date} | 第{day_num}天 | {kana_learned} | {accuracy}% | {new_count} | {review_count} |")
        except Exception:
            continue
    
    # 第二天学习方案
    lines.extend([
        "",
        f"## 🎲 第二天学习方案（{tomorrow}）",
        "",
        "### 新学建议",
        ""
    ])
    
    if new_rows:
        lines.append(f"根据当前进度，建议明天新学：**{new_rows[0]}**")
        lines.append("")
        # 列出该行未学的假名
        row_name = new_rows[0]
        unlearned = [k for k in row_stats[row_name]["kana_list"] if k["hiragana"] not in mastered]
        if unlearned:
            lines.append("**推荐假名：** " + "、".join([k["hiragana"] for k in unlearned]))
            lines.append("")
            lines.append("**单词示例：**")
            for k in unlearned[:3]:  # 显示前 3 个
                lines.append(f"- {k['hiragana']} → {k['katakana']}（{k['mnemonic']}）")
        else:
            lines.append("该行已全部掌握！")
    else:
        lines.append("🎉 所有假名已学完！建议进行全面复习。")
    
    lines.extend([
        "",
        "### 巩固建议",
        ""
    ])
    
    if review_kana:
        lines.append(f"**需要巩固的假名：** {'、'.join(review_kana)}")
        lines.append("")
        lines.append("这些假名正确率较低，建议多复习。")
    else:
        lines.append("（暂无易错假名）")
    
    lines.extend([
        "",
        "### 出题意向",
        ""
    ])
    
    new_kana_for_quiz = []
    if new_rows:
        row_name = new_rows[0]
        new_kana_for_quiz = [k["hiragana"] for k in row_stats[row_name]["kana_list"] if k["hiragana"] not in mastered]
    
    lines.append(f"- **新学假名：** {', '.join(new_kana_for_quiz[:3])}（从 {new_rows[0] if new_rows else '已学完'} 选 3 个）")
    lines.append(f"- **复习假名：** {', '.join(review_kana[:2])}（从易错列表选 2 个）")
    lines.append(f"- **出题类型：** 混合（平假名↔片假名↔读音）")
    lines.append("")
    lines.append("---")
    lines.append("*此文档由 `infer-progress.py` 自动生成，请勿手动修改*")
    
    return "\n".join(lines), new_kana_for_quiz, review_kana

def main():
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 开始分析学习进度并生成档案...")
    
    # 1. 读取配置
    config = load_config()
    if not config:
        print("❌ 配置文件读取失败，退出")
        sys.exit(1)
    
    # 2. 路径
    workspace = os.path.expanduser(config["workspace"]["root"])
    progress_file = os.path.expanduser(config["workspace"]["progress_file"])
    daily_dir = os.path.expanduser(config["workspace"]["daily_dir"])
    profile_md = os.path.join(workspace, "learning-profile.md")
    
    # 3. 读取总体进度
    progress = load_json(progress_file)
    if not progress:
        print("❌ 未找到 progress.json")
        sys.exit(1)
    
    from datetime import timedelta

    # 4. 获取所有假名信息
    all_kana = get_all_kana(config)
    print(f"✅ 已加载 {len(all_kana)} 个假名信息")
    
    # 5. 分析每日答题详情
    print("正在分析每日答题详情...")
    kana_stats = analyze_daily_records(daily_dir, all_kana)
    print(f"✅ 已分析 {len([k for k, v in kana_stats.items() if v['attempts'] > 0])} 个考过的假名")

    # 5.5 生成已学假名复习列表（用于每日摘要）
    mastered_raw = progress.get('mastered', [])
    mastered_kana = list(dict.fromkeys(mastered_raw))  # 去重并保持顺序
    mastered_count = len(mastered_kana)
    
    # 读取 kana-data.json
    kana_data_file = os.path.expanduser(config["workspace"]["kana_data"])
    with open(kana_data_file, "r", encoding="utf-8") as f:
        kana_data = json.load(f)
    
    # 构建假名信息查找表（带 row 信息）
    kana_info_map = {}
    for row in kana_data["rows"]:
        for k in row["kana"]:
            k_with_row = dict(k)  # 复制一份
            k_with_row['row'] = row['row']  # 加上行信息
            kana_info_map[k["hiragana"]] = k_with_row
    
    for i, hira in enumerate(mastered_kana):
        if hira in kana_info_map:
            info = kana_info_map[hira]
            word_romaji = info.get('word_romaji', info['romaji'])
            # 从 mnemonic 提取单词和意思，例如：さくら（樱花）
            mnemonic = info['mnemonic']
            import re
            match = re.match(r'([ぁ-んァ-ヶー]+)（([^）]+)）', mnemonic)
            if match:
                word_display = f"{match.group(1)}（{match.group(2)}, {word_romaji}{match.group(2)}）"
            else:
                word_display = mnemonic

    # 6. 生成 learning-profile.md
    print("正在生成学习档案...")
    profile_content, new_kana, review_kana = generate_learning_profile(progress, kana_stats, all_kana, daily_dir)
    
    with open(profile_md, "w", encoding="utf-8") as f:
        f.write(profile_content)
    
    print(f"✅ 学习档案已更新：{profile_md}")
    
    # 7. 更新 progress.json（添加第二天方案）
    progress["nextDayPlan"] = {
        "date": (datetime.now().date()).strftime("%Y-%m-%d"),
        "newKana": new_kana[:3] if new_kana else [],
        "reviewKana": review_kana[:2] if review_kana else [],
        "suggestedRow": next((row for row in ["あ行", "か行", "さ行", "た行", "な行", "は行", "ま行", "や行", "ら行", "わ行"] 
                               if progress.get("masteredByRow", {}).get(row, {}).get("mastered", 0) < 5), None)
    }
    
    # 7.5 生成 next-day-plan.json（方便程序读取）
    next_day_plan = {
        "date": (datetime.now().date()).strftime("%Y-%m-%d"),
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "newKana": new_kana[:3] if new_kana else [],
        "reviewKana": review_kana[:2] if review_kana else [],
        "suggestedRow": next((row for row in ["あ行", "か行", "さ行", "た行", "な行", "は行", "ま行", "や行", "ら行", "わ行"] 
                               if progress.get("masteredByRow", {}).get(row, {}).get("mastered", 0) < 5), None),
        "quizPlan": {
            "newCount": 3,
            "reviewCount": 2,
            "newKanaForQuiz": new_kana[:3] if new_kana else [],
            "reviewKanaForQuiz": review_kana[:2] if review_kana else [],
            "note": (lambda: f"从{next((row for row in ['あ行', 'か行', 'さ行', 'た行', 'な行', 'は行', 'ま行', 'や行', 'ら行', 'わ行'] if progress.get('masteredByRow', {}).get(row, {}).get('mastered', 0) < 5), '已学完')}选3个新学；从易错列表选2个复习（当前{len(review_kana)}个）")()
        }
    }
    
    next_plan_file = os.path.join(workspace, "next-day-plan.json")
    with open(next_plan_file, "w", encoding="utf-8") as f:
        json.dump(next_day_plan, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 第二天方案已写入 {next_plan_file}")
    print(f"   推荐新学：{new_kana[:3]}")
    print(f"   推荐复习：{review_kana[:2]}")
    
    mastered_count = len(mastered_kana)
    
    print(f"\n✅ 每日沉淀完成！已更新学习档案和第二天的学习方案。\n")
    print("**今日分析摘要：**")
    analyzed_count = len([k for k, v in kana_stats.items() if v['attempts'] > 0])
    print(f"- 已分析 {analyzed_count} 个考过的假名")
    
    # 已学假名完整列表（平假名、片假名、罗马音）
    if mastered_kana:
        print(f"\n**学习进度：**")
        print(f"- 已学假名：{mastered_count} 个")
        print(f"\n**已学假名完整列表：**")
        # 按行分组展示
        from collections import defaultdict
        by_row = defaultdict(list)
        for hira in mastered_kana:
            if hira in kana_info_map:
                info = kana_info_map[hira]
                row = info.get('row', '未知行')
                by_row[row].append(f"{hira}({info['romaji']}) {info['katakana']}")
        
        for row_name in ["あ行", "か行", "さ行", "た行", "な行", "は行", "ま行", "や行", "ら行", "わ行"]:
            if row_name in by_row:
                print(f"- {row_name}：{'  '.join(by_row[row_name])}")
    
    if new_kana:
        print(f"\n- 推荐明天学习：{new_kana[0]}（新学）")
    if review_kana:
        print(f"- 推荐明天复习：{'、'.join(review_kana[:2])}")

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] 全部完成！")

if __name__ == "__main__":
    main()
