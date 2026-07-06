#!/usr/bin/env python3
"""
验证用户回复，更新今日档案（多窗口适配版）
用法：
  # 推荐方式：分离用户回复和引用上下文
  verify-reply.py --user-reply "1C 2B 3B" --full-message "引用上下文..."
  # 旧方式（向后兼容）：只传完整消息
  verify-reply.py --full-message "用户回复: 1C 2B 3B\n\n引用: ..."
- --user-reply 接收用户回复字符串（如 "1C 2B 3B"），可选
- --full-message 接收引用消息上下文，可选（如果传了作为引用上下文）
- 至少需要提供 --user-reply 或 --full-message 之一
- 提供 --user-reply 时按 daily 中保存的答案确定性判分
- 仅在旧式完整消息解析时回退到 LLM
- 匹配回复到正确的窗口（morning/afternoon/evening）
- 更新 daily/*.json 中对应窗口的 questionResults 等字段
- 向后兼容旧格式（扁平 pushed/replied）
读取配置文件：~/.openclaw/workspace/configs/japanese-learning.json
"""

import json
import os
import sys
import re
import argparse
from datetime import datetime

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
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [VERIFY] {msg}\n")


def parse_user_reply(user_reply):
    """
    解析用户回复字符串（如 "1C 2B 3B"）
    返回 dict: {1: "C", 2: "B", 3: "B"}
    如果解析失败返回空 dict
    """
    result = {}
    if not user_reply or not user_reply.strip():
        return result

    # 匹配 "1A" "2B" "3C" 等格式（支持空格分隔或连写如 "1A2B3C"）
    pattern = re.findall(r'(\d+)\s*([A-Da-d])', user_reply)
    for num, letter in pattern:
        result[int(num)] = letter.upper()

    return result


def is_new_format(data):
    """检测是否为多窗口新格式"""
    return "windows" in data


def find_target_file_and_window(config, full_message):
    """
    智能查找目标档案文件和窗口：
    1. 从消息中提取日期（如引用消息的日期）
    2. 从题目ID中提取日期和窗口（格式：q_20260608_morning_001 或 q_20260608_001）
    3. 查找最近的未回复档案
    4. 返回 (target_file, target_date, window_name)
       其中 window_name 可能为 None（旧格式或无法确定）
    """
    daily_dir = os.path.expanduser(config["workspace"]["daily_dir"])
    target_window = None

    # 尝试从题目ID中提取日期和窗口（新格式：q_20260608_morning_001 / w_20260608_morning_001）
    id_match = re.search(r'[qw]_(\d{8})_(\w+)_\d+', full_message)
    if id_match:
        date_str = id_match.group(1)
        target_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        target_window = id_match.group(2)
        target_file = os.path.join(daily_dir, f"{target_date}.json")
        if os.path.isfile(target_file):
            return target_file, target_date, target_window

    # 尝试从题目ID中提取日期（旧格式：q_20260608_001，无窗口名）
    id_match = re.search(r'[qw]_(\d{8})_(\d+)', full_message)
    if id_match:
        date_str = id_match.group(1)
        target_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        target_file = os.path.join(daily_dir, f"{target_date}.json")
        if os.path.isfile(target_file):
            return target_file, target_date, target_window

    # 尝试从消息中提取日期（格式：2026-06-08）
    date_match = re.search(r'202\d-\d{2}-\d{2}', full_message)
    if date_match:
        target_date = date_match.group(0)
        target_file = os.path.join(daily_dir, f"{target_date}.json")
        if os.path.isfile(target_file):
            return target_file, target_date, target_window

    # 查找最近的未回复档案（按文件名倒序）
    if os.path.isdir(daily_dir):
        files = sorted([f for f in os.listdir(daily_dir) if f.endswith('.json')], reverse=True)
        for f in files:
            file_path = os.path.join(daily_dir, f)
            try:
                with open(file_path, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    target_date = f.replace('.json', '')

                    if is_new_format(data):
                        # 新格式：查找有未回复窗口的文件
                        windows = data.get("windows", {})
                        for w_name in ["morning", "afternoon", "evening", "exam"]:
                            w = windows.get(w_name, {})
                            if w.get("pushed") and not w.get("replied"):
                                return file_path, target_date, w_name
                    else:
                        # 旧格式
                        if data.get('pushed') and not data.get('replied'):
                            return file_path, target_date, None
            except:
                continue

    # 默认返回今天的档案路径
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(daily_dir, f"{today}.json"), today, target_window


def get_questions_for_verify(today_data, window_name):
    """
    获取用于验证的题目列表。
    - 新格式：返回指定窗口的题目（如果指定了窗口），否则返回所有窗口的题目
    - 旧格式：返回顶层 questions
    """
    if is_new_format(today_data):
        if window_name:
            win = today_data.get("windows", {}).get(window_name, {})
            return win.get("questions", []), window_name
        else:
            # 未指定窗口，收集所有窗口的题目
            all_qs = []
            windows = today_data.get("windows", {})
            for w_name in ["morning", "afternoon", "evening", "exam"]:
                w = windows.get(w_name, {})
                all_qs.extend(w.get("questions", []))
            return all_qs, None
    else:
        return today_data.get("questions", []), None


def call_openai_compatible_api(api_key, base_url, model, messages):
    """调用 OpenAI 兼容 Chat Completions API"""
    try:
        import requests
    except ImportError:
        print("❌ 缺少 requests 库，请运行: pip3 install requests", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 2000
    }

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise RuntimeError(f"API 调用失败: {e}")


def parse_word_option(option):
    """Parse an option like 'neko 🐱 猫' into romaji/meaning/emoji-ish text."""
    parts = option.split(maxsplit=2)
    return {
        "romaji": parts[0] if parts else "",
        "display": option,
        "meaning": parts[2] if len(parts) >= 3 else "",
    }


def deterministic_parse_user_reply(user_reply, questions, log_file):
    """Build verification results directly from stored questions and answer letters."""
    answers = parse_user_reply(user_reply)
    if not answers:
        return None

    results = []
    correct_count = 0
    for idx, q in enumerate(questions, 1):
        user_answer = answers.get(idx, "?")
        correct_answer = q.get("answer", "?")
        is_correct = user_answer == correct_answer
        if is_correct:
            correct_count += 1

        q_type = q.get("type", "hira2kata")
        result = {
            "questionId": q.get("id", f"q_unknown_{idx:03d}"),
            "question": q.get("q", ""),
            "type": q_type,
            "userAnswer": user_answer,
            "correctAnswer": correct_answer,
            "isCorrect": is_correct,
            "isReview": q.get("isReview", False),
            "isWrong": q.get("isWrong", False),
        }

        options = q.get("options", [])
        selected = ""
        if len(user_answer) == 1 and user_answer.isalpha():
            opt_idx = ord(user_answer.upper()) - ord("A")
            if 0 <= opt_idx < len(options):
                selected = options[opt_idx]

        if q_type in ("word", "word-exam"):
            option_words = q.get("optionWords", [])
            selected_word = {}
            if len(user_answer) == 1 and user_answer.isalpha():
                opt_idx = ord(user_answer.upper()) - ord("A")
                if 0 <= opt_idx < len(option_words):
                    selected_word = option_words[opt_idx]
            parsed_option = parse_word_option(selected) if selected else {}
            result.update({
                "word": q.get("word") or q.get("hiragana", ""),
                "correctKana": q.get("word") or q.get("hiragana", ""),
                "wrongKana": selected_word.get("hiragana", "") if not is_correct else "",
                "romaji": q.get("romaji", ""),
                "meaning": q.get("meaning", ""),
                "emoji": q.get("emoji", ""),
                "selectedRomaji": selected_word.get("romaji") or parsed_option.get("romaji", ""),
                "selectedMeaning": selected_word.get("meaning") or parsed_option.get("meaning", ""),
            })
        else:
            result.update({
                "kana": q.get("kana", ""),
                "kanaHira": q.get("kana", ""),
                "kanaKata": q.get("kanaKata", ""),
                "romaji": q.get("romaji", ""),
                "userAnswerKana": selected,
                "userAnswerRomaji": "",
            })
        results.append(result)

    accuracy = round(correct_count / len(questions) * 100, 2) if questions else 0
    parsed = {
        "userReply": user_reply,
        "questionResults": results,
        "correctCount": correct_count,
        "accuracy": accuracy,
    }
    log(f"确定性解析完成: correctCount={correct_count}, accuracy={accuracy}", log_file)
    return parsed


def llm_parse_full_message(full_message, config, questions, log_file, user_reply=""):
    """用 LLM 推理解析完整消息。
    如果提供了 user_reply，则从中提取用户答案；否则从 full_message 中解析（向后兼容）。
    """

    # 构造题目信息供 LLM 参考
    questions_info = ""
    for i, q in enumerate(questions):
        q_id = q.get("id", f"q_unknown_{i+1:03d}")
        q_text = q.get("q", "")
        options = q.get("options", [])
        answer = q.get("answer", "")
        kana = q.get("kana", "")
        kanaKata = q.get("kanaKata", "")
        options_str = "  ".join([f"{chr(65+j)}. {opt}" for j, opt in enumerate(options)])
        questions_info += (
            f"题目{i+1} (ID: {q_id}): {q_text}\n"
            f"  选项: {options_str}\n"
            f"  正确答案: {answer}\n"
            f"  五十音: {kana} (平假名) / {kanaKata} (片假名)\n\n"
        )

    if user_reply:
        # 新方式：用户答案已从 --user-reply 明确提供，LLM 只需要匹配和判断对错
        parsed_answers = parse_user_reply(user_reply)
        answers_str = "\n".join([f"  第{q_num}题: {ans}" for q_num, ans in sorted(parsed_answers.items())])
        log(f"从 --user-reply 解析到 {len(parsed_answers)} 个答案: {parsed_answers}", log_file)

        prompt = f"""你是一个日语学习系统的答案解析器。

用户的答案已经明确提供如下（来自 --user-reply 参数，格式为"题号 答案字母"）：

{answers_str}

以下是引用推送消息的上下文（包含题目顺序和内容，用于确认匹配关系）：

```
{full_message}
```

以下是本次推送的题目信息（含正确答案，供你判断对错）：

{questions_info}

请将用户的每个答案按顺序匹配到对应的题目（第1题对应questions的第1个，以此类推），判断对错，然后输出严格的 JSON（不要输出 ```json ``` 标记，不要输出任何其他解释文字）：

```json
{{
  "userReply": "用户原始回复内容（如 1A 2B 3C）",
  "questionResults": [
    {{
      "questionId": "题目ID（如 q_20260523_001）",
      "question": "题目文本",
      "kanaHira": "对应的五十音平假名",
      "kanaKata": "对应的五十音片假名",
      "romaji": "对应的罗马音",
      "userAnswer": "用户选择的答案字母（A/B/C）",
      "userAnswerKana": "用户选择的假名（从选项中提取，如 ア）",
      "userAnswerRomaji": "用户选择假名的罗马音",
      "correctAnswer": "正确答案字母（A/B/C）",
      "isCorrect": true
    }}
  ],
  "correctCount": 正确的题目数量（整数）,
  "accuracy": 正确率（浮点数，如66.67）
}}
```

重要要求：
1. 用户的答案已经明确给出（见上方），请按顺序将第1题答案匹配到第1个题目，第2题到第2个，以此类推
2. 根据引用的原始推送消息或题目ID确认匹配关系
3. questionResults 数组长度必须等于题目数量
4. accuracy 是百分比（如 66.67 表示 66.67%），不是小数
5. 只输出 JSON，不要任何多余文字
6. userAnswerKana 和 userAnswerRomaji 必须从用户选择的选项中提取假名和罗马音
7. 如果选项是假名（如 ア (a)），提取假名部分（如 ア）并查找对应的罗马音
"""
    else:
        # 旧方式：从 full_message 中解析（向后兼容）
        prompt = f"""你是一个日语学习系统的答案解析器。

以下是用户回复和原始推送消息的完整内容：

```
{full_message}
```

以下是本次推送的题目信息（供你参考）：

{questions_info}

请仔细分析用户的回复，匹配每道题的答案，然后输出严格的 JSON（不要输出 ```json ``` 标记，不要输出任何其他解释文字）：

```json
{{
  "userReply": "用户原始回复内容（如 1A 2B 3C）",
  "questionResults": [
    {{
      "questionId": "题目ID（如 q_20260523_001）",
      "question": "题目文本",
      "kanaHira": "对应的五十音平假名",
      "kanaKata": "对应的五十音片假名",
      "romaji": "对应的罗马音",
      "userAnswer": "用户选择的答案字母（A/B/C）",
      "userAnswerKana": "用户选择的假名（从选项中提取，如 ア）",
      "userAnswerRomaji": "用户选择假名的罗马音",
      "correctAnswer": "正确答案字母（A/B/C）",
      "isCorrect": true
    }}
  ],
  "correctCount": 正确的题目数量（整数）,
  "accuracy": 正确率（浮点数，如66.67）
}}
```

重要要求：
1. 从完整消息中提取用户的答案（如 1A 2B 3C 格式）
2. 根据引用的原始推送消息或题目ID匹配每道题
3. questionResults 数组长度必须等于题目数量
4. accuracy 是百分比（如 66.67 表示 66.67%），不是小数
5. 只输出 JSON，不要任何多余文字
6. userAnswerKana 和 userAnswerRomaji 必须从用户选择的选项中提取假名和罗马音
7. 如果选项是假名（如 ア (a)），提取假名部分（如 ア）并查找对应的罗马音
"""

    api_key = config["api"]["api_key"]
    base_url = config["api"]["base_url"]
    model = config["api"].get("model", "deepseek-chat")

    log(f"调用 LLM 解析完整消息（长度: {len(full_message)} 字符）...", log_file)
    log(f"完整消息前200字符: {full_message[:200]}", log_file)

    messages = [
        {"role": "system", "content": "你是一个JSON解析器，只输出严格JSON，不输出任何其他内容。"},
        {"role": "user", "content": prompt}
    ]

    try:
        response = call_openai_compatible_api(api_key, base_url, model, messages)
        content = response["choices"][0]["message"]["content"].strip()
        log(f"LLM 返回原始内容: {content[:500]}", log_file)

        # 尝试提取 JSON（可能包含 ```json ``` 包裹）
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
            log("从 ```json ``` 中提取了 JSON", log_file)

        # 也尝试直接找 { 到 } 的内容
        if not content.startswith("{"):
            json_match = re.search(r'(\{.*\})', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
                log("用正则提取了 JSON 内容", log_file)

        parsed = json.loads(content)
        log(f"LLM 解析成功: correctCount={parsed.get('correctCount')}, accuracy={parsed.get('accuracy')}", log_file)
        return parsed

    except json.JSONDecodeError as e:
        log(f"❌ LLM 返回内容不是有效 JSON: {e}", log_file)
        log(f"LLM 原始返回: {content}", log_file)
        # 写入推理错误日志
        error_log = os.path.expanduser(config["logs"]["infer_error_log"])
        with open(error_log, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [ERROR] JSON解析失败: {e}\n")
            f.write(f"[ERROR] LLM 原始返回:\n{content}\n")
            f.write(f"[ERROR] 完整消息:\n{full_message}\n\n")
        raise RuntimeError(f"LLM 返回内容无法解析为 JSON: {content[:200]}")
    except Exception as e:
        log(f"❌ LLM 调用失败: {e}", log_file)
        raise


def match_reply_to_window(today_data, parsed_question_ids):
    """
    根据解析出的题目ID，确定回复属于哪个窗口。
    返回窗口名称，或 None（旧格式 / 无法确定）。
    """
    if not is_new_format(today_data):
        return None

    windows = today_data.get("windows", {})
    for w_name in ["morning", "afternoon", "evening", "exam"]:
        w = windows.get(w_name, {})
        w_q_ids = {q.get("id") for q in w.get("questions", [])}
        if w_q_ids.intersection(parsed_question_ids):
            return w_name

    return None


def format_output(parsed, questions):
    """格式化输出结果"""
    results = parsed.get("questionResults", [])
    correct_count = parsed.get("correctCount", 0)
    accuracy = parsed.get("accuracy", 0)

    # 构建 questionId -> question 详情的映射
    qid_to_question = {}
    for q in questions:
        qid = q.get("id", "")
        if qid:
            qid_to_question[qid] = q

    lines = []
    for i, r in enumerate(results):
        q_num = i + 1
        q_id = r.get("questionId", "")
        # 从 question 列表查找题目详情
        q_detail = qid_to_question.get(q_id, {})
        if (r.get("type") or q_detail.get("type")) in ("word", "word-exam"):
            word = r.get("word") or q_detail.get("word") or q_detail.get("hiragana", "")
            romaji = r.get("romaji") or q_detail.get("romaji", "")
            meaning = r.get("meaning") or q_detail.get("meaning", "")
            emoji = r.get("emoji") or q_detail.get("emoji", "")
            if r.get("isCorrect"):
                lines.append(f"Q{q_num} 题目：{word} ({romaji}) {emoji} {meaning} ✅")
            else:
                selected_romaji = r.get("selectedRomaji", "")
                selected_meaning = r.get("selectedMeaning", "")
                lines.append(f"Q{q_num} 题目：{word} ({romaji}) {emoji} {meaning}")
                lines.append(f"  你的答案：{selected_romaji} {selected_meaning} ❌")
                lines.append(f"  正确答案：{romaji} {meaning} ✅")
            continue

        kanaHira = r.get("kanaHira", "") or q_detail.get("kana", "")
        kanaKata = r.get("kanaKata", "") or q_detail.get("kanaKata", "")
        romaji = r.get("romaji", "") or q_detail.get("romaji", "")

        if r.get("isCorrect"):
            lines.append(f"Q{q_num} 题目：{kanaHira} ({romaji}) / {kanaKata} ({romaji}) ✅")
        else:
            user_answer_kana = r.get("userAnswerKana", "")
            user_answer_romaji = r.get("userAnswerRomaji", "")
            # 查找正确答案的假名和罗马音
            correct_answer_letter = r.get("correctAnswer", "")
            correct_kana = ""
            correct_romaji = ""
            options = q_detail.get("options", [])
            if correct_answer_letter and options:
                try:
                    idx = ord(correct_answer_letter.upper()) - ord("A")
                    if 0 <= idx < len(options):
                        opt = options[idx]
                        # 从选项提取假名和罗马音，格式如 "ア (a)"
                        match = re.match(r"([^\s]+)\s*\(([^)]+)\)", opt)
                        if match:
                            correct_kana = match.group(1)
                            correct_romaji = match.group(2)
                except Exception:
                    pass
            lines.append(f"Q{q_num} 题目：{kanaHira} ({romaji}) / {kanaKata} ({romaji})")
            lines.append(f"  你的答案：{user_answer_kana} ({user_answer_romaji}) ❌")
            lines.append(f"  正确答案：{correct_kana} ({correct_romaji}) ✅")

    lines.append("")
    lines.append(f"📊 本次正确率: {accuracy:.2f}% ({correct_count}/{len(results)})")

    if correct_count == len(results):
        lines.append("🎉 全对！太棒了！")
    elif correct_count >= len(results) * 2 / 3:
        lines.append("👍 不错，再接再厉！")
    elif correct_count >= len(results) / 3:
        lines.append("💪 继续加油，多复习几遍！")
    else:
        lines.append("😅 没关系，先看教学再试试！")

    return "\n".join(lines)


def update_window_data(today_data, window_name, parsed):
    """更新指定窗口的回复数据"""
    if is_new_format(today_data) and window_name:
        win = today_data["windows"].get(window_name, {})
        win["userReply"] = parsed.get("userReply", "")
        win["questionResults"] = parsed.get("questionResults", [])
        win["correctCount"] = parsed.get("correctCount", 0)
        win["accuracy"] = parsed.get("accuracy", 0)
        win["replied"] = True
        win["repliedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    else:
        # 旧格式：直接更新顶层
        today_data["userReply"] = parsed.get("userReply", "")
        today_data["questionResults"] = parsed.get("questionResults", [])
        today_data["correctCount"] = parsed.get("correctCount", 0)
        today_data["accuracy"] = parsed.get("accuracy", 0)
        today_data["replied"] = True
        today_data["repliedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 更新总计数据（新格式）
    if is_new_format(today_data):
        total_correct = 0
        total_questions = 0
        for w_name in ["morning", "afternoon", "evening", "exam"]:
            w = today_data["windows"].get(w_name, {})
            total_correct += w.get("correctCount", 0)
            total_questions += len(w.get("questionResults", []))
        today_data["totalCorrectCount"] = total_correct
        today_data["totalAccuracy"] = round(total_correct / total_questions * 100, 2) if total_questions > 0 else 0


def update_mastered_progress(today_data, config, log_file):
    """根据所有窗口的答题结果更新总体进度（含错题集）"""
    progress_file = os.path.expanduser(config["workspace"]["progress_file"])
    try:
        with open(progress_file, "r", encoding="utf-8") as f:
            progress = json.load(f)

        # 收集所有窗口的题目和结果
        all_questions = []
        all_results = []
        if is_new_format(today_data):
            for w_name in ["morning", "afternoon", "evening", "exam"]:
                w = today_data["windows"].get(w_name, {})
                all_questions.extend(w.get("questions", []))
                all_results.extend(w.get("questionResults", []))
                for sw in w.get("studyWords", []):
                    if sw.get("hiragana"):
                        if "wordIntroduced" not in progress:
                            progress["wordIntroduced"] = []
                        if sw["hiragana"] not in progress["wordIntroduced"]:
                            progress["wordIntroduced"].append(sw["hiragana"])
        else:
            all_questions = today_data.get("questions", [])
            all_results = today_data.get("questionResults", [])

        # 添加今日学习的假名到 mastered（去重）
        for q in all_questions:
            if q.get("type") in ("word", "word-exam"):
                continue
            kana = q.get("kana", "")
            if kana and kana not in progress.get("mastered", []):
                if "mastered" not in progress:
                    progress["mastered"] = []
                progress["mastered"].append(kana)

        progress["masteredCount"] = len(progress["mastered"])

        # === 更新单词学习进度 ===
        if "wordMastered" not in progress:
            progress["wordMastered"] = []
        if "wordWrongList" not in progress:
            progress["wordWrongList"] = []
        if "wordIntroduced" not in progress:
            progress["wordIntroduced"] = []

        normalized_wrong = []
        for item in progress.get("wordWrongList", []):
            if isinstance(item, str):
                normalized_wrong.append({"hiragana": item, "wrongCount": 1})
            elif isinstance(item, dict):
                normalized_wrong.append(item)
        progress["wordWrongList"] = normalized_wrong
        word_wrong_map = {
            (w.get("hiragana") or w.get("word")): w
            for w in progress.get("wordWrongList", [])
            if w.get("hiragana") or w.get("word")
        }
        word_mastered = set(progress.get("wordMastered", []))
        word_introduced = set(progress.get("wordIntroduced", []))

        for q in all_questions:
            if q.get("type") in ("word", "word-exam"):
                word_introduced.add(q.get("word") or q.get("hiragana", ""))

        for r in all_results:
            if r.get("type") not in ("word", "word-exam"):
                continue
            word = r.get("word") or r.get("correctKana", "")
            if not word:
                continue
            if r.get("isCorrect"):
                word_mastered.add(word)
                if word in word_wrong_map:
                    progress["wordWrongList"] = [
                        item for item in progress.get("wordWrongList", [])
                        if (item.get("hiragana") or item.get("word")) != word
                    ]
                    word_wrong_map.pop(word, None)
            else:
                existing = word_wrong_map.get(word)
                if existing:
                    existing["wrongCount"] = existing.get("wrongCount", 0) + 1
                else:
                    item = {
                        "hiragana": word,
                        "romaji": r.get("romaji", ""),
                        "meaning": r.get("meaning", ""),
                        "emoji": r.get("emoji", ""),
                        "wrongCount": 1,
                    }
                    progress["wordWrongList"].append(item)
                    word_wrong_map[word] = item

        progress["wordIntroduced"] = sorted([w for w in word_introduced if w])
        progress["wordMastered"] = sorted([w for w in word_mastered if w])
        progress["wordMasteredCount"] = len(progress["wordMastered"])
        progress["wordWrongList"].sort(key=lambda x: x.get("wrongCount", 1), reverse=True)

        learned_by_day = progress.setdefault("wordMasteredByDay", {})
        record_date = today_data.get("date") or datetime.now().strftime("%Y-%m-%d")
        day_entry = learned_by_day.setdefault(record_date, {"learned": [], "examResults": {}})
        learned_today = set(day_entry.get("learned", []))
        if is_new_format(today_data):
            for w_name in ["morning", "afternoon", "evening"]:
                for sw in today_data.get("windows", {}).get(w_name, {}).get("studyWords", []):
                    if sw.get("hiragana"):
                        learned_today.add(sw["hiragana"])
        learned_today.update(today_data.get("wordsLearned", []))
        day_entry["learned"] = sorted([w for w in learned_today if w])

        exam_results = {}
        for r in all_results:
            if r.get("type") in ("word", "word-exam"):
                word = r.get("word") or r.get("correctKana", "")
                if word:
                    exam_results[word] = {
                        "isCorrect": bool(r.get("isCorrect")),
                        "userAnswer": r.get("userAnswer", ""),
                        "correctAnswer": r.get("correctAnswer", ""),
                        "questionId": r.get("questionId", ""),
                    }
        if exam_results:
            day_entry["examResults"] = exam_results

        # === 更新错题集（wrongKana）===
        # 收集答错的假名
        wrong_in_window = set()
        for r in all_results:
            if r.get("type") in ("word", "word-exam"):
                continue
            if not r.get("isCorrect"):
                hira = r.get("kana") or r.get("kanaHira", "")
                if hira:
                    wrong_in_window.add(hira)

        # 用 kana-data.json 补全错题数据
        kana_data_file = os.path.expanduser(config.get("workspace", {}).get("kana_data", ""))
        kana_lookup = {}
        if kana_data_file and os.path.isfile(kana_data_file):
            try:
                with open(kana_data_file, "r", encoding="utf-8") as kf:
                    kd = json.load(kf)
                for row in kd.get("rows", []):
                    for k in row.get("kana", []):
                        kana_lookup[k["hiragana"]] = {
                            "kata": k["katakana"],
                            "romaji": k["romaji"]
                        }
            except Exception:
                pass

        if "wrongKana" not in progress:
            progress["wrongKana"] = []

        existing_wrong_map = {w["hira"]: w for w in progress["wrongKana"]}

        for hira in wrong_in_window:
            if hira in existing_wrong_map:
                # 已存在，增加错题次数
                existing_wrong_map[hira]["wrongCount"] = existing_wrong_map[hira].get("wrongCount", 0) + 1
            else:
                # 新增错题记录
                info = kana_lookup.get(hira, {"kata": "", "romaji": ""})
                progress["wrongKana"].append({
                    "hira": hira,
                    "kata": info["kata"],
                    "romaji": info["romaji"],
                    "wrongCount": 1
                })

        # 按错题次数排序
        progress["wrongKana"].sort(key=lambda x: x.get("wrongCount", 1), reverse=True)

        progress["lastUpdateTime"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

        log(f"总体进度已更新: masteredCount={progress['masteredCount']}, wordMasteredCount={progress.get('wordMasteredCount', 0)}", log_file)
        if wrong_in_window:
            log(f"错题集更新: {wrong_in_window}", log_file)
        else:
            log(f"本轮无新增错题", log_file)
    except Exception as e:
        log(f"⚠️ 更新总体进度失败: {e}", log_file)


def main():
    parser = argparse.ArgumentParser(description="日语学习答案验证（多窗口LLM推理版）")
    parser.add_argument("--full-message", default="",
                        help="完整消息字符串（引用推送消息上下文，可选；如果只传 --user-reply 则作为上下文）")
    parser.add_argument("--user-reply", default="",
                        help="用户回复字符串（如 1C 2B 3B），可选；提供后优先从该参数提取用户答案")
    args = parser.parse_args()

    full_message = args.full_message
    user_reply = args.user_reply

    # 至少需要提供 --user-reply 或 --full-message 之一
    if not full_message and not user_reply:
        print("❌ 至少需要提供 --user-reply 或 --full-message 参数", file=sys.stderr)
        print("   用法: verify-reply.py --user-reply \"1C 2B 3B\" [--full-message \"引用上下文...\"]", file=sys.stderr)
        sys.exit(1)

    # 加载配置
    config = load_config()

    # 日志路径
    log_dir = os.path.expanduser(config["logs"]["dir"])
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.expanduser(config["logs"]["main_log"])
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    log("=" * 60, log_file)
    log("===== 开始处理用户回复 =====", log_file)
    log(f"收到用户回复: '{user_reply}' (长度: {len(user_reply)} 字符), 完整消息长度: {len(full_message)} 字符", log_file)

    # 智能查找目标档案和窗口
    target_file, target_date, window_name = find_target_file_and_window(config, full_message)
    log(f"目标档案: {target_file} (日期: {target_date}, 窗口: {window_name or '未确定/旧格式'})", log_file)

    if not os.path.isfile(target_file):
        log(f"❌ 目标档案不存在: {target_file}", log_file)
        print("❌ 未找到可回答的题目，请确认是否已推送")
        sys.exit(1)

    # 检查是否是"未来"的档案
    today = datetime.now().strftime("%Y-%m-%d")
    if target_date > today:
        log(f"⚠️ 警告：目标日期 {target_date} 晚于今天 {today}", log_file)
        print(f"⚠️ 题目日期 {target_date} 晚于今天，请确认是否正确")
        sys.exit(1)

    # 读取目标档案
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            today_data = json.load(f)
    except Exception as e:
        log(f"❌ 读取目标档案失败: {e}", log_file)
        sys.exit(1)

    # 记录实际回答的日期
    today_data["_answeredOn"] = today
    today_data["_originalDate"] = target_date

    # 获取用于验证的题目列表
    questions, matched_window = get_questions_for_verify(today_data, window_name)

    # 如果未确定窗口，尝试从题目ID匹配
    if not matched_window and is_new_format(today_data):
        # 从消息中提取所有题目ID
        qid_pattern = re.findall(r'[qw]_\d{8}_\w+_\d+', full_message)
        if not qid_pattern:
            qid_pattern = re.findall(r'[qw]_\d{8}_\d+', full_message)
        if qid_pattern:
            matched_window = match_reply_to_window(today_data, set(qid_pattern))
            if matched_window:
                log(f"通过题目ID匹配到窗口: {matched_window}", log_file)
                questions, _ = get_questions_for_verify(today_data, matched_window)

    # 检查是否已回复（新格式：检查对应窗口；旧格式：检查顶层）
    if is_new_format(today_data) and matched_window:
        win = today_data.get("windows", {}).get(matched_window, {})
        if win.get("replied"):
            log(f"窗口 [{matched_window}] 已回复过，跳过", log_file)
            print(f"ℹ️ {matched_window} 窗口已回复过，等待下次推送")
            sys.exit(0)
    elif not is_new_format(today_data) and today_data.get("replied"):
        log("今日已回复过，跳过", log_file)
        print("ℹ️ 今日已回复过，等待下次推送")
        sys.exit(0)

    if not questions:
        log("❌ 未找到题目列表", log_file)
        print("❌ 未找到可回答的题目")
        sys.exit(1)

    parsed = deterministic_parse_user_reply(user_reply, questions, log_file) if user_reply else None
    if parsed is None:
        # 用 LLM 推理解析完整消息（兼容旧方式）
        try:
            parsed = llm_parse_full_message(full_message, config, questions, log_file, user_reply)
        except Exception as e:
            log(f"❌ LLM 推理失败: {e}", log_file)
            print(f"❌ 答案解析失败，请稍后重试或联系管理员")
            sys.exit(1)

    # 验证解析结果
    results = parsed.get("questionResults", [])

    # 构建 questionId -> question 的映射
    qid_to_q = {}
    for q in questions:
        qid = q.get("id", "")
        if qid:
            qid_to_q[qid] = q

    # 补齐 results 缺失的 isReview 等字段
    for r in results:
        q_id = r.get("questionId", "")
        if q_id in qid_to_q:
            q_detail = qid_to_q[q_id]
            if "isReview" not in r:
                r["isReview"] = q_detail.get("isReview", False)
            if not r.get("kanaHira"):
                r["kanaHira"] = q_detail.get("kana", "")
            if not r.get("kanaKata"):
                r["kanaKata"] = q_detail.get("kanaKata", "")
            if not r.get("romaji"):
                r["romaji"] = q_detail.get("romaji", "")
            if "type" not in r:
                r["type"] = q_detail.get("type", "hira2kata")
            if q_detail.get("type") in ("word", "word-exam"):
                r.setdefault("word", q_detail.get("word") or q_detail.get("hiragana", ""))
                r.setdefault("correctKana", q_detail.get("word") or q_detail.get("hiragana", ""))
                r.setdefault("meaning", q_detail.get("meaning", ""))
                r.setdefault("emoji", q_detail.get("emoji", ""))

    if len(results) != len(questions):
        log(f"⚠️ 解析结果数量({len(results)})与题目数量({len(questions)})不匹配", log_file)
        # 尝试补齐
        while len(results) < len(questions):
            idx = len(results)
            results.append({
                "questionId": questions[idx].get("id", f"q_unknown_{idx+1:03d}"),
                "question": questions[idx].get("q", ""),
                "kana": questions[idx].get("kana", ""),
                "userAnswer": "?",
                "correctAnswer": questions[idx].get("answer", "?"),
                "isCorrect": False
            })
        parsed["questionResults"] = results

    # 记录详细结果到日志
    for r in results:
        q_id = r.get("questionId", "?")
        ua = r.get("userAnswer", "?")
        ca = r.get("correctAnswer", "?")
        ic = "✅" if r.get("isCorrect") else "❌"
        kana = r.get("kana", "?")
        log(f"{q_id}: 用户答={ua} 正确答案={ca} {ic} ({kana})", log_file)

    # 更新对应窗口的数据
    update_window_data(today_data, matched_window, parsed)

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(today_data, f, ensure_ascii=False, indent=2)

    if matched_window:
        log(f"窗口 [{matched_window}] 已更新: correctCount={parsed.get('correctCount')}, accuracy={parsed.get('accuracy')}%, replied=true", log_file)
    else:
        log(f"档案已更新: correctCount={today_data.get('correctCount')}, accuracy={today_data.get('accuracy')}%, replied=true, answeredOn={target_date}", log_file)

    # 更新总体进度
    update_mastered_progress(today_data, config, log_file)

    log("===== 处理完成 =====", log_file)

    # 输出结果
    output = format_output(parsed, questions)

    # 添加日期/窗口提示
    prefix_parts = []
    if target_date != today:
        prefix_parts.append(f"📅 回答 {target_date} 的题目")
    if matched_window:
        window_labels = {"morning": "🌅 早间", "afternoon": "☀️ 午间", "evening": "🌙 晚间", "exam": "🎯 测验"}
        prefix_parts.append(f"{window_labels.get(matched_window, matched_window)}推送")

    if prefix_parts:
        output = " · ".join(prefix_parts) + "\n\n" + output

    print(output)


if __name__ == "__main__":
    main()
