#!/usr/bin/env python3
"""
Generate study word selections and word exam questions.

Default / --new mode is used by daytime study pushes and only returns words.
--exam mode returns questions for an evening recall exam.
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime


CONFIG_FILE = os.path.expanduser("~/.openclaw/workspace/configs/japanese-learning.json")
HIRAGANA = "ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞただちぢっつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽまみむめもゃやゅゆょよらりるれろゎわをんー"
KATAKANA = "ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポマミムメモャヤュユョヨラリルレロヮワヲンー"
KATA_MAP = str.maketrans(HIRAGANA, KATAKANA)


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


def to_katakana(text):
    return text.translate(KATA_MAP)


def normalize_word(word):
    item = dict(word)
    item.setdefault("katakana", to_katakana(item.get("hiragana", "")))
    item.setdefault("similarGroup", [item.get("romaji", "")])
    return item


def normalize_wrong_items(items):
    words = []
    for item in items or []:
        if isinstance(item, str):
            words.append(item)
        elif isinstance(item, dict):
            words.append(item.get("hiragana") or item.get("word") or "")
    return [w for w in words if w]


def get_today_used_words(today_data):
    used = set(today_data.get("wordsLearned", []))
    for win in today_data.get("windows", {}).values():
        for w in win.get("studyWords", []):
            if w.get("hiragana"):
                used.add(w["hiragana"])
        for q in win.get("questions", []):
            word = q.get("word") or q.get("hiragana")
            if q.get("type") in ("word", "word-exam") and word:
                used.add(word)
    return used


def words_by_hiragana(words):
    return {w["hiragana"]: w for w in words}


def select_study_words(words, progress, today_data, count):
    used_today = get_today_used_words(today_data)
    start = int(progress.get("wordStudyIndex", 0) or 0)
    selected = []
    idx = start
    while idx < len(words) and len(selected) < count:
        word = words[idx]
        if word["hiragana"] not in used_today:
            selected.append(word)
        idx += 1
    return selected, idx


def select_review_words(words, progress, count, excluded):
    by_hira = words_by_hiragana(words)
    candidates = []
    for hira in progress.get("wordMastered", []) + progress.get("wordIntroduced", []):
        if hira in by_hira and hira not in excluded and hira not in candidates:
            candidates.append(hira)
    random.shuffle(candidates)
    return [by_hira[h] for h in candidates[:count]]


def select_wrong_words(words, progress, count, excluded):
    by_hira = words_by_hiragana(words)
    selected = []
    wrong_order = normalize_wrong_items(progress.get("wordWrongList", []))
    for hira in wrong_order:
        if hira in by_hira and hira not in excluded:
            selected.append(by_hira[hira])
        if len(selected) >= count:
            break
    return selected


def find_similar_distractors(word, words, count):
    by_romaji = {w["romaji"]: w for w in words}
    selected = []
    seen = {word["hiragana"]}

    for romaji in word.get("similarGroup", []):
        cand = by_romaji.get(romaji)
        if cand and cand["hiragana"] not in seen:
            selected.append(cand)
            seen.add(cand["hiragana"])
        if len(selected) >= count:
            return selected

    # Fallback keeps distractors close by length and first/last sound.
    romaji = word["romaji"]
    fallback = [
        w for w in words
        if w["hiragana"] not in seen
        and (len(w["romaji"]) == len(romaji) or w["romaji"][0] == romaji[0] or w["romaji"][-1] == romaji[-1])
    ]
    random.shuffle(fallback)
    for cand in fallback:
        selected.append(cand)
        seen.add(cand["hiragana"])
        if len(selected) >= count:
            return selected

    rest = [w for w in words if w["hiragana"] not in seen]
    random.shuffle(rest)
    return selected + rest[: count - len(selected)]


def question_for_word(word, all_words, date_key, index, is_review=False, is_wrong=False):
    use_katakana = random.random() < 0.5
    prompt_word = word["katakana"] if use_katakana else word["hiragana"]
    distractors = find_similar_distractors(word, all_words, 3)
    option_words = distractors + [word]
    random.shuffle(option_words)
    answer = chr(65 + option_words.index(word))
    option_mode = "romaji" if use_katakana else "romaji-meaning"

    if option_mode == "romaji":
        options = [w["romaji"] for w in option_words]
    else:
        options = [f"{w['romaji']} {w.get('emoji', '')} {w['meaning']}".strip() for w in option_words]

    return {
        "id": f"w_{date_key}_exam_{index:03d}",
        "type": "word-exam",
        "word": word["hiragana"],
        "hiragana": word["hiragana"],
        "katakana": word["katakana"],
        "romaji": word["romaji"],
        "meaning": word["meaning"],
        "emoji": word.get("emoji", ""),
        "kanaCovered": word.get("kanaCovered", []),
        "difficulty": word.get("difficulty", 1),
        "isReview": is_review,
        "isWrong": is_wrong,
        "promptScript": "katakana" if use_katakana else "hiragana",
        "optionMode": option_mode,
        "q": f"「{prompt_word}」怎么读？",
        "options": options,
        "optionWords": [
            {
                "hiragana": w["hiragana"],
                "katakana": w["katakana"],
                "romaji": w["romaji"],
                "meaning": w["meaning"],
                "emoji": w.get("emoji", ""),
            }
            for w in option_words
        ],
        "answer": answer,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate Japanese word study/exam payloads")
    parser.add_argument("--new", type=int, default=2, help="number of new study words")
    parser.add_argument("--review", type=int, default=1, help="number of review words in exam mode")
    parser.add_argument("--wrong", type=int, default=1, help="number of wrong-list words in exam mode")
    parser.add_argument("--exam", action="store_true", help="generate evening exam questions")
    parser.add_argument("--words", default="", help="comma-separated hiragana words to test in exam mode")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--window", default="manual")
    parser.add_argument("--today-file", default="")
    args = parser.parse_args()

    config = load_config()
    workspace = config["workspace"]
    word_data_file = os.path.expanduser(workspace.get("word_data", "~/.openclaw/workspace/japanese-learning/word-data.json"))
    progress_file = os.path.expanduser(workspace["progress_file"])

    word_data = load_json(word_data_file)
    progress = load_json(progress_file, {})
    today_data = load_json(args.today_file, {}) if args.today_file else {}
    if not word_data or "words" not in word_data:
        print(f"failed to read word data: {word_data_file}", file=sys.stderr)
        sys.exit(1)

    words = [normalize_word(w) for w in word_data["words"]]
    by_hira = words_by_hiragana(words)
    date_key = args.date.replace("-", "")

    if not args.exam:
        selected_new, next_index = select_study_words(words, progress, today_data, args.new)
        print(json.dumps({
            "mode": "word-study",
            "teachingWords": selected_new,
            "nextStudyIndex": next_index,
            "questions": [],
        }, ensure_ascii=False, indent=2))
        return

    requested = [w.strip() for w in args.words.split(",") if w.strip()]
    exam_words = [by_hira[h] for h in requested if h in by_hira]
    excluded = {w["hiragana"] for w in exam_words}

    wrong_words = select_wrong_words(words, progress, args.wrong, excluded)
    excluded.update(w["hiragana"] for w in wrong_words)
    review_words = select_review_words(words, progress, args.review, excluded)

    questions = []
    q_index = 1
    for word in exam_words:
        questions.append(question_for_word(word, words, date_key, q_index, False, False))
        q_index += 1
    for word in wrong_words:
        questions.append(question_for_word(word, words, date_key, q_index, True, True))
        q_index += 1
    for word in review_words:
        questions.append(question_for_word(word, words, date_key, q_index, True, False))
        q_index += 1

    print(json.dumps({
        "mode": "word-exam",
        "examWords": exam_words,
        "reviewWords": review_words,
        "wrongWords": wrong_words,
        "questions": questions,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
