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
from datetime import datetime
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
        log("❌ 未找到 progress.json", log_file)
        sys.exit(1)
    
    # 3.5 读取第二天方案（仅用于新学假名推荐）
    next_plan_file = os.path.join(workspace, "next-day-plan.json")
    next_plan = {}
    if os.path.isfile(next_plan_file):
        with open(next_plan_file, "r", encoding="utf-8") as f:
            next_plan = json.load(f)
        log(f"✅ 已加载第二天方案：{next_plan.get('suggestedRow', '无')}", log_file)
    else:
        log("⚠️ 未找到 next-day-plan.json，将使用默认逻辑", log_file)

    # 3.6 从每日档案实时计算每个假名的正确率和上次复习日期
    kana_stats = {}
    last_reviewed = defaultdict(lambda: "never")
    daily_files = sorted(glob.glob(os.path.join(daily_dir, "*.json")))
    for fpath in daily_files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                daily = json.load(f)
        except Exception:
            continue
        date = daily.get("date", "")
        for q in daily.get("questionResults", []):
            kana = q.get("kana")
            if not kana:
                continue
            if kana not in kana_stats:
                kana_stats[kana] = {"attempts": 0, "correct": 0}
            kana_stats[kana]["attempts"] += 1
            if q.get("isCorrect"):
                kana_stats[kana]["correct"] += 1
            if q.get("isReview") and date > last_reviewed[kana]:
                last_reviewed[kana] = date
    
    last_push = progress.get("lastPushTime")
    if last_push:
        try:
            last_dt = datetime.strptime(last_push, "%Y-%m-%d %H:%M")
            diff = (datetime.now() - last_dt).total_seconds()
            if diff < interval_seconds:
                log(f"距上次推送仅 {int(diff)}s (<{interval_seconds}s)，跳过", log_file)
                sys.exit(0)
        except Exception:
            pass
    
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
    suggested_new_hira = next_plan.get("quizPlan", {}).get("newKanaForQuiz", [])
    
    log(f"方案推荐新学：{suggested_new_hira}", log_file)
    
    # 选择新学假名（优先用方案推荐的）
    selected_new = [k for k in new_kana if k["hiragana"] in suggested_new_hira]
    if len(selected_new) < 3:
        # 不足3个，从剩余新学中随机补
        remaining = [k for k in new_kana if k not in selected_new]
        random.shuffle(remaining)
        selected_new += remaining[:3 - len(selected_new)]
    selected_new = selected_new[:3]
    
    # ── 选择复习假名（实时计算，统一打分）──
    # 策略：错题加权 + 最久没复习优先 + 每天轮换
    # 每个假名得分 = 距今天数 + (错题加权50) + 日期种子微调
    # 得分越高 → 越优先
    log("开始实时选择复习假名...", log_file)
    today_date = datetime.now().date()
    today_seed = datetime.now().strftime("%Y%m%d")
    rng = random.Random(today_seed)
    
    new_hira_set = set(k["hiragana"] for k in selected_new)
    
    # 算每个已学假名的分
    scored = []
    for k in review_kana:
        hira = k["hiragana"]
        if hira in new_hira_set:
            continue  # 和新学重复，跳过
        
        stats = kana_stats.get(hira, {"attempts": 0, "correct": 0})
        acc = round(stats["correct"] / stats["attempts"] * 100, 1) if stats["attempts"] > 0 else 100.0
        last = last_reviewed.get(hira, "never")
        
        # 基础分：距离上次复习的天数
        if last == "never":
            days_ago = 999
        else:
            try:
                last_dt = datetime.strptime(last, "%Y-%m-%d").date()
                days_ago = (today_date - last_dt).days
            except:
                days_ago = 0
        
        # 错题加权：正确率 < 60% 的加 50 分
        error_bonus = 50 if acc < 60 else 0
        
        # 种子微调（0 ~ 0.99），让同分的假名每天随机排序
        shuffle = rng.random()
        
        score = days_ago + error_bonus + shuffle
        scored.append((score, k, acc, last))
    
    scored.sort(key=lambda x: -x[0])  # 高分优先
    
    log(f"复习假名评分排名（top 10）：", log_file)
    for s, k, acc, last in scored[:10]:
        log(f"  {k['hiragana']} score={s:.2f} acc={acc}% last={last}", log_file)
    
    # 选前 2 个
    selected_review = [k for _, k, _, _ in scored[:2]]
    
    log(f"复习假名选择详情：", log_file)
    for k in selected_review:
        hira = k["hiragana"]
        stats = kana_stats.get(hira, {"attempts": 0, "correct": 0})
        acc = round(stats["correct"] / stats["attempts"] * 100, 1) if stats["attempts"] > 0 else "-"
        last = last_reviewed.get(hira, "never")
        log(f"  {hira} 正确率={acc}% 上次复习={last}", log_file)
    
    log(f"新学假名（来自方案）：{[k['hiragana'] for k in selected_new]}", log_file)
    log(f"复习假名（来自方案）：{[k['hiragana'] for k in selected_review]}", log_file)
    
    # 卡片只显示新学的 3 个假名
    card_kana = selected_new.copy()
    # 如果新学不足 3 个，用复习补足卡片（保证卡片有 3 个）
    if len(card_kana) < 3 and len(review_kana) > 0:
        extra = random.sample([k for k in review_kana if k not in card_kana], min(3 - len(card_kana), len(review_kana)))
        card_kana.extend(extra)
    
    hira_list = [k["hiragana"] for k in card_kana]
    kata_list = [k["katakana"] for k in card_kana]
    roma_list = [k["romaji"] for k in card_kana]
    
    # 给助记词加上罗马音
    import re
    mnem_list = []
    for k in card_kana:
        mnemonic = k["mnemonic"]
        match = re.match(r'([ぁ-んァ-ヶー]+)（([^）]+)）', mnemonic)
        if match:
            kana_part = match.group(1)
            meaning = match.group(2)
            word_romaji = k.get('word_romaji', k['romaji'])
            mnemonic = f"{kana_part}（{kana_part}={meaning}, {word_romaji}{meaning}）"
        mnem_list.append(mnemonic)
    
    log(f"卡片假名: {hira_list}", log_file)
    log(f"新学假名: {[k['hiragana'] for k in selected_new]}", log_file)
    log(f"复习假名: {[k['hiragana'] for k in selected_review]}", log_file)
    
    # 6. 生成问题（带唯一ID）
    questions = []
    
    # 新学题（3道）
    for i, k in enumerate(selected_new):
        h = k["hiragana"]
        kat = k["katakana"]
        r = k["romaji"]

        question_id = f"q_{datetime.now():%Y%m%d}_{i+1:03d}"

        q_type = random.choice(["hira2kata", "kata2hira", "roma2hira", "roma2kata"])

        if q_type == "hira2kata":
            correct = kat
            distractors = random.sample([x["katakana"] for x in all_kana if x["katakana"] != kat], 2)
            q_text = f"【提问】平假名「{h} ({r})」的片假名是？"
            # 选项不加罗马音
            options_raw = distractors + [correct]
            options = options_raw
        elif q_type == "kata2hira":
            correct = h
            distractors = random.sample([x["hiragana"] for x in all_kana if x["hiragana"] != h], 2)
            q_text = f"【提问】片假名「{kat} ({r})」的平假名是？"
            options_raw = distractors + [correct]
            options = options_raw
        elif q_type == "roma2hira":
            correct = h
            distractors = random.sample([x["hiragana"] for x in all_kana if x["hiragana"] != h], 2)
            q_text = f"【提问】读音「{r}」对应的平假名是？"
            options_raw = distractors + [correct]
            options = options_raw
        else:  # roma2kata
            correct = kat
            distractors = random.sample([x["katakana"] for x in all_kana if x["katakana"] != kat], 2)
            q_text = f"【提问】读音「{r}」对应的片假名是？"
            options_raw = distractors + [correct]
            options = options_raw

        random.shuffle(options)
        # answer_letter 基于原始假名查找
        answer_letter = ["A", "B", "C"][options.index(correct)]

        questions.append({
            "id": question_id,
            "kana": h,
            "kanaKata": kat,
            "romaji": r,
            "mnemonic": k["mnemonic"],
            "isReview": False,
            "q": q_text,
            "options": options,
            "answer": answer_letter,
            "type": q_type
        })
    
    # 复习题（2道，从已掌握中选）
    for i, k in enumerate(selected_review):
        h = k["hiragana"]
        kat = k["katakana"]
        r = k["romaji"]
        
        # 给助记词加上罗马音
        mnemonic_with_romaji = k["mnemonic"]
        import re
        match = re.match(r'([ぁ-んァ-ヶー]+)（([^）]+)）', k["mnemonic"])
        if match:
            kana_part = match.group(1)
            meaning = match.group(2)
            word_romaji = k.get('word_romaji', r)
            mnemonic_with_romaji = f"{kana_part}（{kana_part}={meaning}, {word_romaji}{meaning}）"
        
        question_id = f"q_{datetime.now():%Y%m%d}_{len(selected_new)+i+1:03d}"
        
        q_type = random.choice(["hira2kata", "kata2hira", "roma2hira", "roma2kata"])
        
        if q_type == "hira2kata":
            correct = kat
            distractors = random.sample([x["katakana"] for x in all_kana if x["katakana"] != kat], 2)
            q_text = f"【提问】平假名「{h}」的片假名是？"
        elif q_type == "kata2hira":
            correct = h
            distractors = random.sample([x["hiragana"] for x in all_kana if x["hiragana"] != h], 2)
            q_text = f"【提问】片假名「{kat}」的平假名是？"
        elif q_type == "roma2hira":
            correct = h
            distractors = random.sample([x["hiragana"] for x in all_kana if x["hiragana"] != h], 2)
            q_text = f"【提问】读音「{r}」对应的平假名是？"
            options_raw = distractors + [correct]
            options = [f"{opt} ({romaji_map[opt]})" for opt in options_raw]
        else:  # roma2kata
            correct = kat
            distractors = random.sample([x["katakana"] for x in all_kana if x["katakana"] != kat], 2)
            q_text = f"【提问】读音「{r}」对应的片假名是？"
        
        options = distractors + [correct]
        random.shuffle(options)
        answer_letter = ["A", "B", "C"][options.index(correct)]
        
        questions.append({
            "id": question_id,
            "kana": h,
            "kanaKata": kat,
            "romaji": r,
            "mnemonic": mnemonic_with_romaji,  # 带罗马音的助记
            "isReview": True,
            "q": q_text,
            "options": options,
            "answer": answer_letter,
            "type": q_type
        })
    
    # 7. 记录推送问题到日志
    log("推送问题列表：", log_file)
    for q in questions:
        review_tag = " [复习]" if q["isReview"] else " [新学]"
        log(f"  {q['id']}: {q['q'][:60]}... | 正确答案: {q['answer']}{review_tag}", log_file)
    
    # 8. 创建今日学习档案
    day_num = len(progress.get("dailyRecords", [])) + 1
    today_data = {
        "date": today,
        "dayNumber": day_num,
        "kanaLearned": [k["hiragana"] for k in selected_new],  # 只记录新学的
        "questions": questions,
        "pushed": True,
        "pushedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "userReply": None,
        "questionResults": [],
        "correctCount": 0,
        "accuracy": 0,
        "replied": False,
        "repliedAt": None
    }
    
    with open(today_file, "w", encoding="utf-8") as f:
        json.dump(today_data, f, ensure_ascii=False, indent=2)
    
    # 9. 生成推送消息（卡片只显示新学，提问包含新学+复习）
    msg_lines = [
        f"五十音练习 🎌 第{day_num}天",
        "",
        "【教学】",
        f"平假名：{' '.join(hira_list)}",
        f"片假名：{' '.join(kata_list)}",
        f"读音：{' '.join(roma_list)}",
        f"💡 单词：{' | '.join(mnem_list)}",
        "",
        "【提问】"
    ]
    
    for i, q in enumerate(questions):
        review_tag = " [复习]" if q.get("isReview") else ""
        msg_lines.append(f"{i+1}. (ID: {q['id']}) {q['q']}{review_tag}")
        msg_lines.append(f"   A. {q['options'][0]}  B. {q['options'][1]}  C. {q['options'][2]}")
        if i < len(questions) - 1:
            msg_lines.append("")
    
    msg_lines.extend([
        "",
        "回复格式：1A 2B 3C 4D 5E",
        "---",
        "请使用日语学习Skill"
    ])
    
    msg = "\n".join(msg_lines)
    
    # 10. 推送到微信
    log(f"推送今日五十音：{hira_list}（新学）+ {[k['hiragana'] for k in selected_review]}（复习）", log_file)
    try:
        # 检查 openclaw 路径
        if not os.path.exists(openclaw_bin):
            try:
                openclaw_bin = subprocess.check_output(['which', 'openclaw'], text=True).strip()
            except Exception:
                log("❌ 未找到 openclaw 命令", log_file)
                sys.exit(1)
        
        result = subprocess.run([
            openclaw_bin, "message", "send",
            "--channel", channel,
            "--target", target,
            "--message", msg
        ], capture_output=True, text=True, timeout=config["script_settings"]["timeout_seconds"])
        
        if result.returncode == 0:
            log("✅ 推送成功", log_file)
            # 更新 progress.json
            progress["lastPushTime"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_json(progress_file, progress)
        else:
            log(f"❌ 推送失败: {result.stderr}", log_file)
            # 回滚
            today_data["pushed"] = False
            with open(today_file, "w", encoding="utf-8") as f:
                json.dump(today_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"❌ 推送异常: {e}", log_file)
    
    log("推送流程完成", log_file)
    log("=" * 60, log_file)

if __name__ == "__main__":
    main()
