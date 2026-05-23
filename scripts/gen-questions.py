#!/usr/bin/env python3
"""
生成今日学习档案 + 问题
用法：python3 gen-questions.py <9个假名> <3个片假名> <3个读音> <3个联想> <today_file> <progress_file>
"""

import json
import random
import sys
import os

if len(sys.argv) < 13:
    print("用法: gen-questions.py hira1 hira2 hira3 kata1 kata2 kata3 roma1 roma2 roma3 mnem1 mnem2 mnem3 today_file progress_file")
    sys.exit(1)

# 解析参数（每个假名一组：hira, kata, roma, mnem）
args = sys.argv[1:]  # 跳过脚本名
# 前12个是3组假名，最后是2个文件路径
hira_list = args[0:3]
kata_list = args[3:6]
roma_list = args[6:9]
mnem_list = args[9:12]
today_file = args[12]
progress_file = args[13]

# 读取 kana-data.json 用于生成干扰项
kana_data_file = os.path.expanduser("~/.openclaw/workspace/japanese-learning/kana-data.json")
with open(kana_data_file, "r", encoding="utf-8") as f:
    data = json.load(f)

all_hira = []
all_kata = []
all_roma = []
for row in data["rows"]:
    for k in row["kana"]:
        all_hira.append(k["hiragana"])
        all_kata.append(k["katakana"])
        all_roma.append(k["romaji"])

questions = []
for i in range(3):
    h = hira_list[i]
    k = kata_list[i]
    r = roma_list[i]
    
    # 随机选择问题类型
    q_type = random.choice(["hira2kata", "kata2hira", "roma2hira", "roma2kata"])
    
    if q_type == "hira2kata":
        # 平假名 → 片假名
        correct = k
        distractors = random.sample([x for x in all_kata if x != k], 2)
        q_text = f"【提问】平假名「{h}」的片假名是？"
    elif q_type == "kata2hira":
        # 片假名 → 平假名
        correct = h
        distractors = random.sample([x for x in all_hira if x != h], 2)
        q_text = f"【提问】片假名「{k}」的平假名是？"
    elif q_type == "roma2hira":
        # 读音 → 平假名
        correct = h
        distractors = random.sample([x for x in all_hira if x != h], 2)
        q_text = f"【提问】读音「{r}」对应的平假名是？"
    else:  # roma2kata
        # 读音 → 片假名
        correct = k
        distractors = random.sample([x for x in all_kata if x != k], 2)
        q_text = f"【提问】读音「{r}」对应的片假名是？"
    
    options = distractors + [correct]
    random.shuffle(options)
    answer_letter = ["A", "B", "C"][options.index(correct)]
    
    questions.append({
        "id": i+1,
        "q": q_text,
        "options": options,
        "answer": answer_letter
    })

# 读取当前进度获取 dayNumber
with open(progress_file, "r", encoding="utf-8") as f:
    progress = json.load(f)

day_num = len(progress.get("dailyRecords", [])) + 1
today_str = os.path.basename(today_file).replace(".json", "")

# 创建今日档案
today_data = {
    "date": today_str,
    "dayNumber": day_num,
    "kanaLearned": hira_list,
    "questions": questions,
    "userReply": None,
    "correctCount": 0,
    "totalCount": 3,
    "accuracy": 0,
    "pushed": True,
    "replied": False,
    "pushedAt": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
}

with open(today_file, "w", encoding="utf-8") as f:
    json.dump(today_data, f, ensure_ascii=False, indent=2)

print("✅ 今日学习档案已创建")
for i, q in enumerate(questions):
    print(f"Q{q['id']}: {q['q']} | 正确答案: {q['answer']}")
