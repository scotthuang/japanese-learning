#!/usr/bin/env python3
"""
日语五十音推送策略脚本（3时段推送版）
由心跳（每30分钟）调用
每天3个时间窗口：早间(08-12)、午间(13-17)、晚间(19-22)
每个窗口推送4题（1新学+2复习+1错题集），各窗口题目不重复
读取配置文件：~/.openclaw/workspace/configs/japanese-learning.json
"""

import json
import os
import sys
import random
import re
import glob
import subprocess
import fcntl
from datetime import datetime, timedelta
from collections import defaultdict

# 配置文件路径
CONFIG_FILE = os.path.expanduser("~/.openclaw/workspace/configs/japanese-learning.json")

WINDOW_LABELS = {
    "morning": "早间推送",
    "afternoon": "午间推送",
    "evening": "晚间推送",
}
WINDOW_EMOJI = {
    "morning": "🌅",
    "afternoon": "☀️",
    "evening": "🌙",
}

# 文件锁路径（防止并发执行）
LOCK_FILE = "/tmp/japanese-push.lock"

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
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [PUSH] {msg}\n")

def load_json(path):
    """读取 JSON 文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return None

def save_json(path, data):
    """保存 JSON 文件"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_current_window(config):
    """
    判断当前时间落在哪个窗口。
    返回窗口名称（morning/afternoon/evening）或 None（静默时段）。
    """
    now = datetime.now()
    hour = now.hour

    windows_config = config["push_strategy"].get("windows", {
        "morning": {"start": 8, "end": 12},
        "afternoon": {"start": 13, "end": 17},
        "evening": {"start": 19, "end": 22},
    })

    for name, w in windows_config.items():
        if w["start"] <= hour < w["end"]:
            return name

    return None

def get_window_label(window_name):
    """获取窗口的中文标签（含emoji）"""
    emoji = WINDOW_EMOJI.get(window_name, "")
    label = WINDOW_LABELS.get(window_name, window_name)
    return f"{emoji} {label}"

def get_used_kana_in_today(today_data):
    """收集当天所有窗口已使用的假名（平假名），避免重复"""
    used_new = set()
    used_review = set()
    used_wrong = set()
    windows = today_data.get("windows", {})
    for w_name, w_data in windows.items():
        if w_data.get("pushed"):
            for q in w_data.get("questions", []):
                kana = q.get("kana", "")
                if kana:
                    if q.get("isWrong"):
                        used_wrong.add(kana)
                    elif q.get("isReview"):
                        used_review.add(kana)
                    else:
                        used_new.add(kana)
    return used_new, used_review, used_wrong

def init_today_file(today, day_number):
    """初始化今日档案（3个窗口都为空）"""
    return {
        "date": today,
        "dayNumber": day_number,
        "kanaLearned": [],
        "windows": {
            "morning": {
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
        "totalCorrectCount": 0,
        "totalAccuracy": 0,
    }

def migrate_old_format(today_data, today, day_number):
    """
    将旧格式（扁平 pushed/replied）迁移到新格式（windows）。
    旧数据整体放入 morning 窗口作为唯一的已推送窗口。
    """
    if "windows" in today_data:
        return today_data  # 已经是新格式

    new_data = init_today_file(today, day_number)
    new_data["kanaLearned"] = today_data.get("kanaLearned", [])

    was_pushed = today_data.get("pushed", False)
    was_replied = today_data.get("replied", False)

    # 将旧数据放入 morning 窗口
    morning = new_data["windows"]["morning"]
    morning["pushed"] = was_pushed
    morning["pushedAt"] = today_data.get("pushedAt")
    morning["questions"] = today_data.get("questions", [])
    morning["userReply"] = today_data.get("userReply")
    morning["questionResults"] = today_data.get("questionResults", [])
    morning["correctCount"] = today_data.get("correctCount", 0)
    morning["accuracy"] = today_data.get("accuracy", 0)
    morning["replied"] = was_replied
    morning["repliedAt"] = today_data.get("repliedAt")

    # 如果已推送且已回复，标记 morning 窗口完成
    if was_pushed and was_replied:
        pass  # 其他窗口仍然可以推送

    new_data["totalCorrectCount"] = today_data.get("correctCount", 0)
    new_data["totalAccuracy"] = today_data.get("accuracy", 0)

    return new_data

def all_windows_pushed(today_data):
    """检查是否所有3个窗口都已推送"""
    windows = today_data.get("windows", {})
    for w_name in ["morning", "afternoon", "evening"]:
        w = windows.get(w_name, {})
        if not w.get("pushed", False):
            return False
    return True

def select_new_kana(all_kana, mastered, used_today_new, suggested_new_hira, count=1):
    """
    选择新学假名：优先用方案推荐的，避免当天已用过的。
    返回选中的假名列表。
    """
    new_kana = [k for k in all_kana if k["hiragana"] not in mastered]

    if not new_kana:
        return []

    # 从推荐中选，排除当天已用
    from_suggested = [
        k for k in new_kana
        if k["hiragana"] in suggested_new_hira and k["hiragana"] not in used_today_new
    ]

    selected = []
    if from_suggested:
        random.shuffle(from_suggested)
        selected = from_suggested[:count]

    # 不足时从剩余未学中补
    if len(selected) < count:
        remaining = [k for k in new_kana if k not in selected and k["hiragana"] not in used_today_new]
        random.shuffle(remaining)
        needed = count - len(selected)
        selected += remaining[:needed]

    return selected[:count]

def select_review_kana(all_kana, mastered, used_today_review, suggested_review_hira, count=2):
    """
    选择复习假名：从已掌握中选，优先易错，排除当天已用过的。
    """
    review_kana = [k for k in all_kana if k["hiragana"] in mastered]

    if not review_kana:
        return []

    # 从推荐易错中选，排除当天已用
    from_suggested = [
        k for k in review_kana
        if k["hiragana"] in suggested_review_hira and k["hiragana"] not in used_today_review
    ]

    selected = []
    if from_suggested:
        random.shuffle(from_suggested)
        selected = from_suggested[:count]

    # 不足时从剩余已掌握中补
    if len(selected) < count:
        remaining = [k for k in review_kana if k not in selected and k["hiragana"] not in used_today_review]
        random.shuffle(remaining)
        needed = count - len(selected)
        selected += remaining[:needed]

    return selected[:count]

def select_wrong_kana(all_kana, wrong_kana_list, used_today_wrong, count=1):
    """
    从错题集中选择假名进行再次练习。
    优先选错题次数多的，排除当天已用过的。
    """
    if not wrong_kana_list:
        return []

    # 按错题次数排序（多的优先）
    sorted_wrong = sorted(wrong_kana_list, key=lambda x: x.get("wrongCount", 1), reverse=True)

    selected = []
    for wk in sorted_wrong:
        hira = wk["hira"]
        if hira in used_today_wrong:
            continue
        # 在 all_kana 中找到对应假名数据
        for k in all_kana:
            if k["hiragana"] == hira:
                selected.append(k)
                break
        if len(selected) >= count:
            break

    # 如果不够，从剩余中补
    if len(selected) < count:
        for wk in sorted_wrong:
            hira = wk["hira"]
            already_selected = set(k["hiragana"] for k in selected)
            if hira in already_selected or hira in used_today_wrong:
                continue
            for k in all_kana:
                if k["hiragana"] == hira:
                    selected.append(k)
                    break
            if len(selected) >= count:
                break

    return selected[:count]

def generate_questions_for_window(selected_new, selected_review, selected_wrong, all_kana, window_name):
    """
    为一个窗口生成题目列表。
    selected_new: 新学假名列表（通常1个）
    selected_review: 复习假名列表（通常2个）
    selected_wrong: 错题集假名列表（通常1个）
    返回 questions 列表。
    """
    questions = []
    # 收集所有假名用于生成干扰项
    all_hira_list = []
    all_kata_list = []
    for k in all_kana:
        all_hira_list.append(k["hiragana"])
        all_kata_list.append(k["katakana"])

    def make_question(k, is_review, is_wrong, q_index):
        hira = k["hiragana"]
        kata = k["katakana"]
        romaji = k["romaji"]
        mnemonic = k.get("mnemonic", "")

        q_type = random.choice(["hira2kata", "kata2hira", "roma2hira"])

        if is_wrong:
            prefix = "【错题】"
        elif is_review:
            prefix = "【复习】"
        else:
            prefix = "【新学】"

        if q_type == "hira2kata":
            options = [x for x in all_kata_list if x != kata]
            distractors = random.sample(options, min(2, len(options)))
            opts = distractors + [kata]
            random.shuffle(opts)
            q = {
                "id": f"q_{datetime.now():%Y%m%d}_{window_name}_{q_index:03d}",
                "kana": hira,
                "kanaKata": kata,
                "romaji": romaji,
                "mnemonic": mnemonic,
                "isReview": is_review,
                "isWrong": is_wrong,
                "q": f"平假名「{hira} ({romaji})」的片假名是？ {prefix}",
                "options": opts,
                "answer": chr(65 + opts.index(kata)),
                "type": "hira2kata",
            }
        elif q_type == "kata2hira":
            options = [x for x in all_hira_list if x != hira]
            distractors = random.sample(options, min(2, len(options)))
            opts = distractors + [hira]
            random.shuffle(opts)
            q = {
                "id": f"q_{datetime.now():%Y%m%d}_{window_name}_{q_index:03d}",
                "kana": hira,
                "kanaKata": kata,
                "romaji": romaji,
                "mnemonic": mnemonic,
                "isReview": is_review,
                "isWrong": is_wrong,
                "q": f"片假名「{kata} ({romaji})」的平假名是？ {prefix}",
                "options": opts,
                "answer": chr(65 + opts.index(hira)),
                "type": "kata2hira",
            }
        else:  # roma2hira
            options = [x for x in all_hira_list if x != hira]
            distractors = random.sample(options, min(2, len(options)))
            opts = distractors + [hira]
            random.shuffle(opts)
            q = {
                "id": f"q_{datetime.now():%Y%m%d}_{window_name}_{q_index:03d}",
                "kana": hira,
                "kanaKata": kata,
                "romaji": romaji,
                "mnemonic": mnemonic,
                "isReview": is_review,
                "isWrong": is_wrong,
                "q": f"读音「{romaji}」对应的平假名是？ {prefix}",
                "options": opts,
                "answer": chr(65 + opts.index(hira)),
                "type": "roma2hira",
            }
        return q

    q_idx = 1
    # 新学题目
    for k in selected_new:
        questions.append(make_question(k, is_review=False, is_wrong=False, q_index=q_idx))
        q_idx += 1

    # 复习题目
    for k in selected_review:
        questions.append(make_question(k, is_review=True, is_wrong=False, q_index=q_idx))
        q_idx += 1

    # 错题集题目
    for k in selected_wrong:
        questions.append(make_question(k, is_review=True, is_wrong=True, q_index=q_idx))
        q_idx += 1

    return questions

def build_push_message(selected_new, selected_review, selected_wrong, questions, window_name, day_number):
    """构建微信推送消息"""
    window_label = get_window_label(window_name)

    total_q = len(questions)
    lines = [f"{window_label} — 五十音练习 🎌 第{day_number}天", ""]

    # 新学部分
    if selected_new:
        new_hira = " ".join([k["hiragana"] for k in selected_new])
        new_kata = " ".join([k["katakana"] for k in selected_new])
        new_roma = " ".join([k["romaji"] for k in selected_new])
        words = []
        for k in selected_new:
            words.append(f"{k['hiragana']}（{k['mnemonic']}）")

        lines.append("【新学】")
        lines.append(f"平假名：{new_hira}")
        lines.append(f"片假名：{new_kata}")
        lines.append(f"读音：{new_roma}")
        lines.append(f"💡 联想：{' | '.join(words)}")

    # 复习提示
    if selected_review:
        review_hira = " ".join([k["hiragana"] for k in selected_review])
        lines.append(f"")
        lines.append(f"【复习】{review_hira}")

    # 错题集提示
    if selected_wrong:
        wrong_hira = " ".join([k["hiragana"] for k in selected_wrong])
        lines.append(f"")
        lines.append(f"【错题回顾】{wrong_hira} ⚠️")

    lines.append("")
    lines.append("【提问】")

    for i, q in enumerate(questions):
        options_str = " ".join([f"{chr(65+j)}. {opt}" for j, opt in enumerate(q["options"])])
        if q.get("isWrong"):
            tag = "错题"
        elif q.get("isReview"):
            tag = "复习"
        else:
            tag = "新学"
        lines.append(f"{i+1}. (ID: {q['id']}) [{tag}] {q['q']}")
        lines.append(f"   {options_str}")

    lines.append("")
    lines.append(f"回复格式：1A 2B 3C 4D（共{total_q}题）")
    lines.append("---")
    lines.append("请使用日语学习Skill")

    return "\n".join(lines)

def generate_daily_summary(config, log_file):
    """生成每日学习总结（昨日答题情况）"""
    daily_dir = os.path.expanduser(config["workspace"]["daily_dir"])

    # 计算昨天的日期
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")
    yesterday_file = os.path.join(daily_dir, f"{yesterday_str}.json")

    if not os.path.isfile(yesterday_file):
        log(f"昨日 ({yesterday_str}) 无档案，跳过总结", log_file)
        return None

    try:
        with open(yesterday_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log(f"❌ 读取昨日档案失败: {e}", log_file)
        return None

    # 统计所有窗口的答题情况
    windows = data.get("windows", {})
    total_questions = []
    total_results = []
    total_correct = 0
    total_accuracy = 0
    all_replied = False

    if windows:
        # 新格式：多窗口
        for w_name, w_data in windows.items():
            total_questions.extend(w_data.get("questions", []))
            total_results.extend(w_data.get("questionResults", []))
            total_correct += w_data.get("correctCount", 0)
            if w_data.get("replied"):
                all_replied = True
    else:
        # 旧格式：扁平结构
        total_questions = data.get("questions", [])
        total_results = data.get("questionResults", [])
        total_correct = data.get("correctCount", 0)
        all_replied = data.get("replied", False)

    kana_learned = data.get("kanaLearned", [])
    total_q_count = len(total_questions)

    if not all_replied or not total_results:
        summary = f"""📅 {yesterday_str} 学习总结

⚠️ 昨日未答题
累计已学：{len(kana_learned)} 个假名"""
        log(f"昨日未答题", log_file)
        return summary

    accuracy = (total_correct / len(total_results) * 100) if total_results else 0

    # 构建总结
    lines = [f"📅 {yesterday_str} 学习总结"]
    lines.append("")
    lines.append(f"✅ 正确率: {accuracy:.2f}% ({total_correct}/{len(total_results)})")

    # 显示错题
    wrong_qs = [r for r in total_results if not r.get("isCorrect")]
    if wrong_qs:
        lines.append("")
        lines.append("❌ 错题回顾:")
        for r in wrong_qs:
            kana_hira = r.get("kanaHira", "") or r.get("kana", "")
            kana_kata = r.get("kanaKata", "")
            romaji = r.get("romaji", "")
            user_ans = r.get("userAnswerKana", "") or r.get("userAnswer", "")
            ca = r.get("correctAnswer", "")
            lines.append(f"  • {kana_hira} ({romaji}) / {kana_kata} ({romaji})")
            lines.append(f"    你的答案: {user_ans} ❌  正确答案: {ca} ✅")

    lines.append("")
    lines.append(f"📚 累计已学: {len(kana_learned)} 个假名")

    return "\n".join(lines)


def acquire_lock():
    """获取文件锁，防止并发执行。成功返回 fd，失败返回 None。"""
    try:
        lock_fd = open(LOCK_FILE, 'w')
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(f"pid={os.getpid()}\nstarted={datetime.now():%Y-%m-%d %H:%M:%S}\n")
        lock_fd.flush()
        return lock_fd
    except (IOError, OSError):
        return None


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
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # 从配置读取推送参数
    push_config = config["push_strategy"]
    new_per_window = push_config.get("new_per_window", 1)
    review_per_window = push_config.get("review_per_window", 2)
    wrong_per_window = push_config.get("wrong_per_window", 1)
    questions_per_window = push_config.get("questions_per_window", 4)

    # 从配置读取微信参数
    wechat_config = config["wechat"]
    channel = wechat_config["channel"]
    target = wechat_config["target"]

    # 从配置读取路径
    openclaw_bin = config["paths"]["openclaw_bin"]

    # 获取文件锁，防止并发执行
    lock_fd = acquire_lock()
    if lock_fd is None:
        log("⚠️ 发现已有实例在运行（文件锁），跳过本次推送", log_file)
        sys.exit(0)
    log("🔒 已获取推送锁", log_file)

    try:
        log("=" * 60, log_file)
        log("心跳触发推送检查（3时段4题推送模式）", log_file)

        # 1. 确保 daily 目录存在
        os.makedirs(daily_dir, exist_ok=True)

        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        today_file = os.path.join(daily_dir, f"{today}.json")

        # 2. 判断当前时间窗口
        current_window = get_current_window(config)

        if current_window is None:
            hour = now.hour
            silent_start = push_config.get("silent_start", 22)
            silent_end = push_config.get("silent_end", 8)
            if hour >= silent_start or hour < silent_end:
                log(f"当前时间 {now:%H:%M} 在静默时段（{silent_start}:00-{silent_end}:00），不推送", log_file)
            else:
                log(f"当前时间 {now:%H:%M} 不在任何推送窗口内（窗口间隙），不推送", log_file)
            sys.exit(0)

        log(f"当前窗口: {current_window} ({get_window_label(current_window)})", log_file)

        # 3. 读取今日档案
        today_data = None
        if os.path.isfile(today_file):
            today_data = load_json(today_file)
            if today_data is None:
                log(f"❌ 读取今日档案失败: {today_file}", log_file)
                sys.exit(1)

            # 检测并迁移旧格式
            if "windows" not in today_data:
                log("检测到旧格式档案，正在迁移到新格式...", log_file)
                # 获取 day number
                progress = load_json(progress_file)
                day_number = progress.get("masteredCount", 0) + 1 if progress else 1
                today_data = migrate_old_format(today_data, today, day_number)
                save_json(today_file, today_data)
                log("旧格式迁移完成", log_file)

        # 4. 读取进度文件
        progress = load_json(progress_file)
        if not progress:
            log("❌ 无法读取进度文件", log_file)
            sys.exit(1)

        day_number = progress.get("masteredCount", 0) + 1

        # 5. 如果今日档案不存在，初始化
        if today_data is None:
            today_data = init_today_file(today, day_number)
            log(f"初始化今日档案: {today_file}", log_file)

        # 6. 检查当前窗口是否已推送
        windows = today_data.get("windows", {})
        current_win_data = windows.get(current_window, {})

        if current_win_data.get("pushed", False):
            log(f"窗口 [{current_window}] 已推送（{current_win_data.get('pushedAt')}），跳过", log_file)
            sys.exit(0)

        # 7. 检查所有窗口是否都已推送
        if all_windows_pushed(today_data):
            log("所有3个窗口已推送完毕，今日不再推送", log_file)
            sys.exit(0)

        # 8. 选择假名
        with open(kana_data_file, "r", encoding="utf-8") as f:
            kana_data = json.load(f)

        # 构建假名列表
        all_kana = []
        for row in kana_data["rows"]:
            for k in row["kana"]:
                all_kana.append(k)

        mastered = set(progress.get("mastered", []))

        # 收集当天已用假名（现在返回3个集合）
        used_new, used_review, used_wrong = get_used_kana_in_today(today_data)

        # 从方案读取推荐
        next_day_plan = progress.get("nextDayPlan", {})
        quiz_plan = next_day_plan.get("quizPlan", {})
        suggested_new_hira = quiz_plan.get("newKanaForQuiz", [])
        suggested_review_hira = quiz_plan.get("reviewKanaForQuiz", [])
        wrong_kana_list = progress.get("wrongKana", [])

        log(f"当天已用新学假名: {used_new}", log_file)
        log(f"当天已用复习假名: {used_review}", log_file)
        log(f"当天已用错题集假名: {used_wrong}", log_file)
        log(f"方案推荐新学: {suggested_new_hira}", log_file)
        log(f"方案推荐复习: {suggested_review_hira}", log_file)
        log(f"错题集共 {len(wrong_kana_list)} 个假名", log_file)

        # 选择新学假名
        selected_new = select_new_kana(all_kana, mastered, used_new, suggested_new_hira, new_per_window)

        # 选择复习假名
        selected_review = select_review_kana(all_kana, mastered, used_review, suggested_review_hira, review_per_window)

        # 选择错题集假名（优先错题，排除当天已用的错题假名）
        selected_wrong = select_wrong_kana(all_kana, wrong_kana_list, used_wrong, wrong_per_window)

        # 边界处理：如果没有新学假名了
        if not selected_new:
            log("⚠️ 没有新的假名可学，本次错题集+复习", log_file)
            # 不填充新学位置，仍然用复习+错题

        # 边界处理：如果没有复习假名
        if not selected_review:
            log("⚠️ 没有可复习的假名，本次仅使用错题集+新学", log_file)

        # 边界处理：如果没有错题集假名（全部答对的情况）
        if not selected_wrong:
            log("✅ 没有错题集假名（全部答对），跳过错题集题目", log_file)

        log(f"选中新学: {[k['hiragana'] for k in selected_new]}", log_file)
        log(f"选中复习: {[k['hiragana'] for k in selected_review]}", log_file)
        log(f"选中错题集: {[k['hiragana'] for k in selected_wrong]}", log_file)

        # 9. 生成题目
        questions = generate_questions_for_window(selected_new, selected_review, selected_wrong, all_kana, current_window)

        # 10. 构建推送消息
        msg = build_push_message(selected_new, selected_review, selected_wrong, questions, current_window, day_number)
        log(f"推送消息：\n{msg}", log_file)

        # 11. 调用 openclaw message send 推送
        cmd = [
            openclaw_bin, "message", "send",
            "--channel", channel,
            "--target", target,
            "--message", msg,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                log("✅ 推送成功", log_file)

                # 更新当前窗口为已推送
                current_win_data["pushed"] = True
                current_win_data["pushedAt"] = now.strftime("%Y-%m-%d %H:%M")
                current_win_data["questions"] = questions

                # 更新当天已学假名列表（去重）
                existing_learned = set(today_data.get("kanaLearned", []))
                for k in selected_new:
                    existing_learned.add(k["hiragana"])
                today_data["kanaLearned"] = list(existing_learned)

                # 检查所有窗口是否都已推送
                if all_windows_pushed(today_data):
                    today_data["allWindowsPushed"] = True
                    log("🎉 所有3个窗口已推送完毕！", log_file)

                save_json(today_file, today_data)

                # 更新进度文件的最后推送时间
                progress["lastPushTime"] = now.strftime("%Y-%m-%d %H:%M")
                save_json(progress_file, progress)

            else:
                log(f"❌ 推送失败: {result.stderr}", log_file)
        except Exception as e:
            log(f"❌ 推送异常: {e}", log_file)

        log("推送流程完成", log_file)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        log("🔓 已释放推送锁", log_file)

if __name__ == "__main__":
    main()
