#!/usr/bin/env python3
"""
Generate word recognition questions for the Japanese learning push system.

Output is JSON so push-strategy.py can embed the questions in the daily file.
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime


CONFIG_FILE = os.path.expanduser("~/.openclaw/workspace/configs/japanese-learning.json")


def load_json(path, default=None):
    try:
        with open(os.path.expanduser(path), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def load_config():
    config = load_json(CONFIG_FILE)
    if not config:
        print(f"failed to read config: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)
    return config


def get_today_used_words(today_data):
    used = set()
    for win in today_data.get("windows", {}).values():
        for q in win.get("questions", []):
            word = q.get("word") or q.get("hiragana")
            if q.get("type") == "word" and word:
                used.add(word)
    return used


def collect_wrong_words_from_daily(daily_dir):
    wrong = {}
    if not os.path.isdir(daily_dir):
        return []

    for filename in sorted(os.listdir(daily_dir), reverse=True):
        if not filename.endswith(".json"):
            continue
        data = load_json(os.path.join(daily_dir, filename), {})
        result_groups = []
        if "windows" in data:
            for win in data.get("windows", {}).values():
                result_groups.extend(win.get("questionResults", []))
        else:
            result_groups.extend(data.get("questionResults", []))

        for r in result_groups:
            if r.get("type") != "word" or r.get("isCorrect", True):
                continue
            word = r.get("word") or r.get("correctKana")
            if not word:
                continue
            item = wrong.setdefault(word, {"hiragana": word, "wrongCount": 0})
            item["wrongCount"] += 1
            for key in ["romaji", "meaning", "emoji"]:
                if r.get(key):
                    item[key] = r[key]

    return sorted(wrong.values(), key=lambda x: x.get("wrongCount", 0), reverse=True)


def question_for_word(word, all_words, date_key, window, index, is_review=False, is_wrong=False):
    distractor_pool = [w for w in all_words if w["hiragana"] != word["hiragana"]]
    distractors = random.sample(distractor_pool, min(3, len(distractor_pool)))
    options_words = distractors + [word]
    random.shuffle(options_words)
    answer = chr(65 + options_words.index(word))

    return {
        "id": f"w_{date_key}_{window}_{index:03d}",
        "type": "word",
        "word": word["hiragana"],
        "hiragana": word["hiragana"],
        "romaji": word["romaji"],
        "meaning": word["meaning"],
        "emoji": word.get("emoji", ""),
        "kanaCovered": word.get("kanaCovered", []),
        "difficulty": word.get("difficulty", 1),
        "isReview": is_review,
        "isWrong": is_wrong,
        "q": f"「{word['hiragana']}」怎么读？",
        "options": [
            f"{w['romaji']} {w.get('emoji', '')} {w['meaning']}".strip()
            for w in options_words
        ],
        "optionWords": [
            {
                "hiragana": w["hiragana"],
                "romaji": w["romaji"],
                "meaning": w["meaning"],
                "emoji": w.get("emoji", ""),
            }
            for w in options_words
        ],
        "answer": answer,
    }


def select_words(words, progress, today_data, new_count, review_count, wrong_count, daily_dir):
    used_today = get_today_used_words(today_data)
    introduced = set(progress.get("wordIntroduced", []))
    mastered = set(progress.get("wordMastered", []))
    wrong_items = progress.get("wordWrongList", []) or collect_wrong_words_from_daily(daily_dir)
    wrong_order = [w.get("hiragana") or w.get("word") for w in wrong_items if w.get("hiragana") or w.get("word")]

    by_hira = {w["hiragana"]: w for w in words}
    selected_wrong = []
    for hira in wrong_order:
        if hira in by_hira and hira not in used_today:
            selected_wrong.append(by_hira[hira])
        if len(selected_wrong) >= wrong_count:
            break

    blocked = used_today | {w["hiragana"] for w in selected_wrong}
    new_pool = [w for w in words if w["hiragana"] not in introduced and w["hiragana"] not in mastered and w["hiragana"] not in blocked]
    random.shuffle(new_pool)
    selected_new = new_pool[:new_count]

    blocked |= {w["hiragana"] for w in selected_new}
    review_candidates = list(mastered | introduced)
    review_pool = [by_hira[h] for h in review_candidates if h in by_hira and h not in blocked]
    random.shuffle(review_pool)
    selected_review = review_pool[:review_count]

    return selected_new, selected_review, selected_wrong


def main():
    parser = argparse.ArgumentParser(description="Generate Japanese word questions")
    parser.add_argument("--new", type=int, default=2, help="number of new words")
    parser.add_argument("--review", type=int, default=1, help="number of review words")
    parser.add_argument("--wrong", type=int, default=1, help="number of wrong-list words")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--window", default="manual")
    parser.add_argument("--today-file", default="")
    args = parser.parse_args()

    config = load_config()
    workspace = config["workspace"]
    word_data_file = os.path.expanduser(workspace.get("word_data", "~/.openclaw/workspace/japanese-learning/word-data.json"))
    progress_file = os.path.expanduser(workspace["progress_file"])
    daily_dir = os.path.expanduser(workspace["daily_dir"])

    word_data = load_json(word_data_file)
    progress = load_json(progress_file, {})
    today_data = load_json(args.today_file, {}) if args.today_file else {}
    if not word_data or "words" not in word_data:
        print(f"failed to read word data: {word_data_file}", file=sys.stderr)
        sys.exit(1)

    words = word_data["words"]
    selected_new, selected_review, selected_wrong = select_words(
        words, progress, today_data, args.new, args.review, args.wrong, daily_dir
    )

    date_key = args.date.replace("-", "")
    questions = []
    q_index = 1
    for word in selected_new:
        questions.append(question_for_word(word, words, date_key, args.window, q_index, False, False))
        q_index += 1
    for word in selected_review:
        questions.append(question_for_word(word, words, date_key, args.window, q_index, True, False))
        q_index += 1
    for word in selected_wrong:
        questions.append(question_for_word(word, words, date_key, args.window, q_index, True, True))
        q_index += 1

    print(json.dumps({
        "mode": "word",
        "teachingWords": selected_new,
        "reviewWords": selected_review,
        "wrongWords": selected_wrong,
        "questions": questions,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
