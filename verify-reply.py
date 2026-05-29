#!/usr/bin/env python3
"""
验证用户回复，更新今日档案
用法：verify-reply.py <用户回复> <今日档案.json> <日志文件>
"""
import json
import sys
import re
from datetime import datetime

if len(sys.argv) < 4:
    print("用法：verify-reply.py <用户回复> <今日档案> <日志文件>")
    sys.exit(1)

user_reply = sys.argv[1]
today_file = sys.argv[2]
log_file = sys.argv[3]

def log(msg):
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [SKILL] {msg}\n")

# 1. 记录原始回复
log("===== 开始处理用户回复 =====")
log(f"原始回复: {user_reply}")

# 2. 解析用户回复（1A 2B 3C）
pattern = r'(\d+)\s*([A-Ca-c])'
matches = re.findall(pattern, user_reply)
if not matches:
    log(f"❌ 未能解析答案，用户回复: {user_reply}")
    print("❌ 答案格式不正确，请使用 1A 2B 3C 格式回复")
    sys.exit(1)

user_answers = {int(num): ans.upper() for num, ans in matches}
log(f"解析到的答案: {user_answers}")

# 3. 读取今日档案
with open(today_file, "r", encoding="utf-8") as f:
    today = json.load(f)

# 4. 验证每个答案
correct_count = 0
for q in today["questions"]:
    q_id = q["id"]
    correct = q["answer"]
    user_ans = user_answers.get(q_id, "?")
    
    if user_ans == correct:
        log(f"Q{q_id}: 用户答={user_ans} 正确答案={correct} ✅")
        correct_count += 1
        print(f"Q{q_id} ✅")
    else:
        q_text = q["q"][:60] + "..."
        log(f"Q{q_id}: 用户答={user_ans} 正确答案={correct} ❌")
        print(f"Q{q_id} ❌ {q_text}")
        print(f"   (正确答案: {correct})")

# 5. 计算正确率
accuracy = round(correct_count / len(today["questions"]) * 100, 2) if today["questions"] else 0
log(f"总计: {correct_count}/{len(today['questions'])}，正确率: {accuracy}%")
print(f"\n📊 今日正确率: {accuracy}% ({correct_count}/{len(today['questions'])})")

# 6. 更新今日档案
today["userReply"] = user_reply
today["correctCount"] = correct_count
today["accuracy"] = accuracy
today["replied"] = True
today["repliedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")

with open(today_file, "w", encoding="utf-8") as f:
    json.dump(today, f, ensure_ascii=False, indent=2)

log(f"今日档案已更新: correctCount={correct_count}, accuracy={accuracy}%, replied=true")

# 7. 调用混元 API 推理
log("开始调用混元 API 推理...")
try:
    import subprocess
    result = subprocess.run([
        "/Users/scotthuang/.openclaw/workspace/japanese-learning/infer-progress.py"
    ], capture_output=True, text=True, timeout=60)
    if result.returncode == 0:
        log("混元 API 推理完成")
        # 读取推理结果
        with open("/Users/scotthuang/.openclaw/workspace/japanese-learning/progress.json", "r", encoding="utf-8") as pf:
            prog = json.load(pf)
        log(f"推理结果: masteredCount={prog.get('masteredCount')}, accuracyRate={prog.get('accuracyRate')}, trend={prog.get('trend', 'N/A')}")
    else:
        log(f"❌ 混元 API 调用失败: {result.stderr}")
except Exception as e:
    log(f"❌ 推理异常: {e}")

log("===== 处理完成 =====")
