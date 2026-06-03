#!/usr/bin/env python3
"""
验证用户回复，更新今日档案（大改造版）
用法：verify-reply.py --full-message "完整消息字符串"
- 只接收 --full-message 参数
- 用 LLM 推理解析完整消息（不用正则）
- 更新 daily/*.json 的 questionResults 等字段
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
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [VERIFY] {msg}\n")


def get_today_file(config):
    """根据日期推理今日档案路径"""
    daily_dir = os.path.expanduser(config["workspace"]["daily_dir"])
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(daily_dir, f"{today}.json")


def call_hunyuan_api(api_key, base_url, model, messages):
    """调用混元 API"""
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


def llm_parse_full_message(full_message, config, today_data, log_file):
    """用 LLM 推理解析完整消息"""

    # 构造题目信息供 LLM 参考
    questions_info = ""
    for i, q in enumerate(today_data.get("questions", [])):
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

    prompt = f"""你是一个日语学习系统的答案解析器。

以下是用户回复和原始推送消息的完整内容：

```
{full_message}
```

以下是今日推送的题目信息（供你参考）：

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
    model = config["api"].get("model", "hy3-preview")

    log(f"调用 LLM 解析完整消息（长度: {len(full_message)} 字符）...", log_file)
    log(f"完整消息前200字符: {full_message[:200]}", log_file)

    messages = [
        {"role": "system", "content": "你是一个JSON解析器，只输出严格JSON，不输出任何其他内容。"},
        {"role": "user", "content": prompt}
    ]

    try:
        response = call_hunyuan_api(api_key, base_url, model, messages)
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


def format_output(parsed, today_data=None):
    """格式化输出结果"""
    results = parsed.get("questionResults", [])
    correct_count = parsed.get("correctCount", 0)
    accuracy = parsed.get("accuracy", 0)

    # 构建 questionId -> question 详情的映射
    qid_to_question = {}
    if today_data:
        for q in today_data.get("questions", []):
            qid = q.get("id", "")
            if qid:
                qid_to_question[qid] = q

    lines = []
    for i, r in enumerate(results):
        q_num = i + 1
        q_id = r.get("questionId", "")
        # 从 today_data 查找题目详情
        q_detail = qid_to_question.get(q_id, {})
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
    lines.append(f"📊 今日正确率: {accuracy:.2f}% ({correct_count}/{len(results)})")

    if correct_count == len(results):
        lines.append("🎉 全对！太棒了！")
    elif correct_count >= len(results) * 2 / 3:
        lines.append("👍 不错，再接再厉！")
    elif correct_count >= len(results) / 3:
        lines.append("💪 继续加油，多复习几遍！")
    else:
        lines.append("😅 没关系，先看教学再试试！")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="日语学习答案验证（LLM推理版）")
    parser.add_argument("--full-message", required=True,
                        help="完整消息字符串（用户回复 + 引用的原始推送消息）")
    args = parser.parse_args()

    full_message = args.full_message

    # 加载配置
    config = load_config()

    # 日志路径
    log_dir = os.path.expanduser(config["logs"]["dir"])
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.expanduser(config["logs"]["main_log"])
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    log("=" * 60, log_file)
    log("===== 开始处理用户回复 =====", log_file)
    log(f"收到完整消息（长度: {len(full_message)} 字符）", log_file)

    # 推理今日档案路径
    today_file = get_today_file(config)
    log(f"今日档案路径: {today_file}", log_file)

    if not os.path.isfile(today_file):
        log(f"❌ 今日档案不存在: {today_file}", log_file)
        print("❌ 今日暂无推送题目，请等待推送后再回复")
        sys.exit(1)

    # 读取今日档案
    try:
        with open(today_file, "r", encoding="utf-8") as f:
            today_data = json.load(f)
    except Exception as e:
        log(f"❌ 读取今日档案失败: {e}", log_file)
        sys.exit(1)

    if today_data.get("replied"):
        log("今日已回复过，跳过", log_file)
        print("ℹ️ 今日已回复过，等待下次推送")
        sys.exit(0)

    # 用 LLM 推理解析完整消息
    try:
        parsed = llm_parse_full_message(full_message, config, today_data, log_file)
    except Exception as e:
        log(f"❌ LLM 推理失败: {e}", log_file)
        print(f"❌ 答案解析失败，请稍后重试或联系管理员")
        sys.exit(1)

    # 验证解析结果
    results = parsed.get("questionResults", [])
    questions = today_data.get("questions", [])
    # 构建 questionId -> question 的映射，用于补充 isReview 等字段
    qid_to_q = {}
    for q in questions:
        qid = q.get("id", "")
        if qid:
            qid_to_q[qid] = q

    # 补齐 results 缺失的 isReview 字段（从今日题目里取）
    for r in results:
        q_id = r.get("questionId", "")
        if q_id in qid_to_q:
            q_detail = qid_to_q[q_id]
            if "isReview" not in r:
                r["isReview"] = q_detail.get("isReview", False)
            # 也补齐 kanaHira 如果缺失
            if not r.get("kanaHira"):
                r["kanaHira"] = q_detail.get("kana", "")
            if not r.get("kanaKata"):
                r["kanaKata"] = q_detail.get("kanaKata", "")
            if not r.get("romaji"):
                r["romaji"] = q_detail.get("romaji", "")

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

    # 更新今日档案
    today_data["userReply"] = parsed.get("userReply", "")
    today_data["questionResults"] = parsed.get("questionResults", [])
    today_data["correctCount"] = parsed.get("correctCount", 0)
    today_data["accuracy"] = parsed.get("accuracy", 0)
    today_data["replied"] = True
    today_data["repliedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(today_file, "w", encoding="utf-8") as f:
        json.dump(today_data, f, ensure_ascii=False, indent=2)

    log(f"今日档案已更新: correctCount={today_data['correctCount']}, accuracy={today_data['accuracy']}%, replied=true", log_file)

    # 更新总体进度（将今日学习的假名加入 mastered 列表）
    progress_file = os.path.expanduser(config["workspace"]["progress_file"])
    try:
        with open(progress_file, "r", encoding="utf-8") as f:
            progress = json.load(f)

        # 添加今日学习的假名到 mastered
        for q in today_data.get("questions", []):
            kana = q.get("kana", "")
            if kana and kana not in progress.get("mastered", []):
                if "mastered" not in progress:
                    progress["mastered"] = []
                progress["mastered"].append(kana)

        progress["masteredCount"] = len(progress["mastered"])
        progress["lastUpdateTime"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

        log(f"总体进度已更新: masteredCount={progress['masteredCount']}", log_file)
    except Exception as e:
        log(f"⚠️ 更新总体进度失败: {e}", log_file)

    log("===== 处理完成 =====", log_file)

    # 输出结果
    output = format_output(parsed, today_data)
    print(output)


if __name__ == "__main__":
    main()
