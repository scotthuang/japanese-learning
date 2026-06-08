#!/usr/bin/env python3
"""
日语五十音推送策略脚本（3新学+2复习版）
由心跳（每30分钟）调用
读取配置文件：~/.openclaw/workspace/configs/japanese-learning.json
"""

import json
import os
import sys
import random
import re
import glob
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict

# 配置文件路径
CONFIG_FILE = os.path.expanduser("~/.openclaw/workspace/configs/japanese-learning.json")

def load_config():
    """加载配置文件"""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}", file=sys.stderr)
        sys.exit(1)

def log(msg, log_file):
    """写日志"""
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [PUSH] {msg}\n")

def load_json(path):
    """读取 JSON 文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"❌ 读取 {path} 失败: {e}", log_file)
        return None

def save_json(path, data):
    """保存 JSON 文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    # 加载配置
    config = load_config()
    
    # 从配置读取路径
    workspace = os.path.expanduser(config["workspace"]["root"])
    progress_file = os.path.expanduser(config["workspace"]["progress_file"])
    daily_dir = os.path.expanduser(config["workspace"]["daily_dir"])
    kana_data_file = os.path.expanduser(config["workspace"]["kana_data"])
    
    # 日志路径
    log_dir = os.path.expanduser(config["logs"]["dir"])
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.expanduser(config["logs"]["main_log"])
    
    # 从配置读取推送参数
    push_config = config["push_strategy"]
    interval_seconds = push_config["interval_seconds"]
    random_probability = push_config["random_push_probability"]
    questions_per_day = 5  # 改为 5 道题（3新+2复习）
    
    # 从配置读取微信参数
    wechat_config = config["wechat"]
    channel = wechat_config["channel"]
    target = wechat_config["target"]
    
    # 从配置读取路径
    openclaw_bin = config["paths"]["openclaw_bin"]
    
    log("=" * 60, log_file)
    log("心跳触发推送检查（3新学+2复习模式）", log_file)
    
    # 1. 确保 daily 目录存在
    os.makedirs(daily_dir, exist_ok=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    today_file = os.path.join(daily_dir, f"{today}.json")
    
    # 2. 检查今天是否已推送
    if os.path.isfile(today_file):
        today_data = load_json(today_file)
        if today_data and today_data.get("pushed"):
            if not today_data.get("replied"):
                log("今日已推送，但尚未收到回复，跳过", log_file)
                sys.exit(0)
            else:
                log("今日已推送且已回复，跳过", log_file)
                sys.exit(0)
    
    # 3. 检查距上次推送时间
    progress = load_json(progress_file)
    if not progress:
        log("❌ 无法读取进度文件", log_file)
        sys.exit(1)
    
    last_push_time = progress.get("lastPushTime")
    if last_push_time:
        last_push_dt = datetime.strptime(last_push_time, "%Y-%m-%d %H:%M")
        hours_since_last_push = (datetime.now() - last_push_dt).total_seconds() / 3600
        if hours_since_last_push < 2:
            log(f"距上次推送仅 {hours_since_last_push:.1f} 小时，跳过", log_file)
            sys.exit(0)
    
    # 4. 随机决定是否推送
    if random.randint(0, 99) >= random_probability:
        log(f"随机未命中（概率{random_probability}%），本次不推送", log_file)
        sys.exit(0)
    
    # 5. 选择假名（3新学 + 2复习）
    mastered = set(progress.get("mastered", []))
    
    with open(kana_data_file, "r", encoding="utf-8") as f:
        kana_data = json.load(f)
    
    # 所有假名
    all_kana = []
    all_hira = []
    all_kata = []
    all_roma = []
    romaji_map = {}  # 罗马音查找表：假名 -> 罗马音
    for row in kana_data["rows"]:
        for k in row["kana"]:
            all_kana.append(k)
            all_hira.append(k["hiragana"])
            all_kata.append(k["katakana"])
            all_roma.append(k["romaji"])
            romaji_map[k["hiragana"]] = k["romaji"]
            romaji_map[k["katakana"]] = k["romaji"]
    
    # 未掌握的假名（新学）
    new_kana = [k for k in all_kana if k["hiragana"] not in mastered]
    # 已掌握的假名（复习）
    review_kana = [k for k in all_kana if k["hiragana"] in mastered]
    
    if not new_kana:
        log("所有假名已学完！", log_file)
        sys.exit(0)
    
    # 从第二天方案读取推荐假名（仅用于新学）
    suggested_new_hira = progress.get("nextDayPlan", {}).get("quizPlan", {}).get("newKanaForQuiz", [])
    
    log(f"方案推荐新学：{suggested_new_hira}", log_file)
    
    # 选择新学假名（优先用方案推荐的）
    selected_new = [k for k in new_kana if k["hiragana"] in suggested_new_hira]
    if len(selected_new) < 3:
        # 不足3个，从剩余新学中随机补
        remaining = [k for k in new_kana if k not in selected_new]
        random.shuffle(remaining)
        selected_new += remaining[:3 - len(selected_new)]
    selected_new = selected_new[:3]
    
    # 选择复习假名（从已掌握中随机选2个）
    if review_kana:
        random.shuffle(review_kana)
        selected_review = review_kana[:2]
    else:
        selected_review = []
    
    # 6. 生成今日档案
    day_number = progress.get("masteredCount", 0) + 1
    today_data = {
        "date": today,
        "dayNumber": day_number,
        "kanaLearned": [k["hiragana"] for k in selected_new],
        "questions": [],
        "pushed": False,
        "replied": False,
        "userReply": None,
        "questionResults": [],
        "correctCount": 0,
        "accuracy": 0
    }
    
    # 生成题目（3新学 + 2复习）
    questions = []
    
    # 新学题目（3道）
    for k in selected_new:
        hira = k["hiragana"]
        kata = k["katakana"]
        romaji = k["romaji"]
        mnemonic = k.get("mnemonic", "")
        
        # 随机选择题目类型
        q_type = random.choice(["hira2kata", "kata2hira", "roma2hira"])
        
        if q_type == "hira2kata":
            # 平假名 -> 片假名
            options = [k2["katakana"] for k2 in random.sample(all_kana, 2) if k2["katakana"] != kata]
            options.append(kata)
            random.shuffle(options)
            q = {
                "id": f"q_{datetime.now():%Y%m%d}_{len(questions)+1:03d}",
                "kana": hira,
                "kanaKata": kata,
                "romaji": romaji,
                "mnemonic": mnemonic,
                "isReview": False,
                "q": f"【提问】平假名「{hira} ({romaji})」的片假名是？",
                "options": options,
                "answer": chr(65 + options.index(kata)),
                "type": "hira2kata"
            }
        elif q_type == "kata2hira":
            # 片假名 -> 平假名
            options = [k2["hiragana"] for k2 in random.sample(all_kana, 2) if k2["hiragana"] != hira]
            options.append(hira)
            random.shuffle(options)
            q = {
                "id": f"q_{datetime.now():%Y%m%d}_{len(questions)+1:03d}",
                "kana": hira,
                "kanaKata": kata,
                "romaji": romaji,
                "mnemonic": mnemonic,
                "isReview": False,
                "q": f"【提问】片假名「{kata} ({romaji})」的平假名是？",
                "options": options,
                "answer": chr(65 + options.index(hira)),
                "type": "kata2hira"
            }
        else:
            # 罗马音 -> 平假名
            options = [k2["hiragana"] for k2 in random.sample(all_kana, 2) if k2["hiragana"] != hira]
            options.append(hira)
            random.shuffle(options)
            q = {
                "id": f"q_{datetime.now():%Y%m%d}_{len(questions)+1:03d}",
                "kana": hira,
                "kanaKata": kata,
                "romaji": romaji,
                "mnemonic": mnemonic,
                "isReview": False,
                "q": f"【提问】读音「{romaji}」对应的平假名是？",
                "options": options,
                "answer": chr(65 + options.index(hira)),
                "type": "roma2hira"
            }
        questions.append(q)
    
    # 复习题目（2道）
    for k in selected_review:
        hira = k["hiragana"]
        kata = k["katakana"]
        romaji = k["romaji"]
        mnemonic = k.get("mnemonic", "")
        
        # 复习题目类型
        q_type = random.choice(["hira2kata", "kata2hira", "roma2hira"])
        
        if q_type == "hira2kata":
            options = [k2["katakana"] for k2 in random.sample(all_kana, 2) if k2["katakana"] != kata]
            options.append(kata)
            random.shuffle(options)
            q = {
                "id": f"q_{datetime.now():%Y%m%d}_{len(questions)+1:03d}",
                "kana": hira,
                "kanaKata": kata,
                "romaji": romaji,
                "mnemonic": mnemonic,
                "isReview": True,
                "q": f"【提问】平假名「{hira} ({romaji})」的片假名是？ [复习]",
                "options": options,
                "answer": chr(65 + options.index(kata)),
                "type": "hira2kata"
            }
        elif q_type == "kata2hira":
            options = [k2["hiragana"] for k2 in random.sample(all_kana, 2) if k2["hiragana"] != hira]
            options.append(hira)
            random.shuffle(options)
            q = {
                "id": f"q_{datetime.now():%Y%m%d}_{len(questions)+1:03d}",
                "kana": hira,
                "kanaKata": kata,
                "romaji": romaji,
                "mnemonic": mnemonic,
                "isReview": True,
                "q": f"【提问】片假名「{kata} ({romaji})」的平假名是？ [复习]",
                "options": options,
                "answer": chr(65 + options.index(hira)),
                "type": "kata2hira"
            }
        else:
            options = [k2["hiragana"] for k2 in random.sample(all_kana, 2) if k2["hiragana"] != hira]
            options.append(hira)
            random.shuffle(options)
            q = {
                "id": f"q_{datetime.now():%Y%m%d}_{len(questions)+1:03d}",
                "kana": hira,
                "kanaKata": kata,
                "romaji": romaji,
                "mnemonic": mnemonic,
                "isReview": True,
                "q": f"【提问】读音「{romaji}」对应的平假名是？ [复习]",
                "options": options,
                "answer": chr(65 + options.index(hira)),
                "type": "roma2hira"
            }
        questions.append(q)
    
    today_data["questions"] = questions
    
    # 7. 保存今日档案
    save_json(today_file, today_data)
    log(f"今日档案已创建: {today_file}", log_file)
    
    # 8. 推送题目
    # 构建推送消息
    kana_list = [k["hiragana"] for k in selected_new]
    kata_list = [k["katakana"] for k in selected_new]
    romaji_list = [k["romaji"] for k in selected_new]
    
    msg = f"""五十音练习 🎌 第{day_number}天

【教学】
平假名：{' '.join(kana_list)}
片假名：{' '.join(kata_list)}
读音：{' '.join(romaji_list)}
💡 单词：{kana_list[0]}（{romaji_list[0]}） | {kana_list[1]}（{romaji_list[1]}） | {kana_list[2]}（{romaji_list[2]}）

【提问】
"""
    
    for i, q in enumerate(questions):
        options_str = " ".join([f"{chr(65+j)}. {opt}" for j, opt in enumerate(q["options"])])
        msg += f"{i+1}. (ID: {q['id']}) {q['q']}\n   {options_str}\n"
    
    msg += """
回复格式：1A 2B 3C 4D 5E
---
请使用日语学习Skill"""
    
    log(f"推送消息：\n{msg}", log_file)
    
    # 调用 openclaw message send
    cmd = [
        openclaw_bin, "message", "send",
        "--channel", channel,
        "--target", target,
        "--message", msg
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            log("✅ 推送成功", log_file)
            # 更新档案为已推送
            today_data["pushed"] = True
            today_data["pushedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_json(today_file, today_data)
            
            # 更新进度文件的最后推送时间
            progress["lastPushTime"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_json(progress_file, progress)
        else:
            log(f"❌ 推送失败: {result.stderr}", log_file)
    except Exception as e:
        log(f"❌ 推送异常: {e}", log_file)
    
    log("推送流程完成", log_file)

if __name__ == "__main__":
    main()
