# 日语学习系统大改造 - 实施文档

**日期：** 2026-05-23（初版）/ 2026-06-10（3时段推送改造）  
**状态：** ✅ 已实施  
**目标：** LLM 只负责传话，Skill 自己用 LLM 推理解析完整消息，判断对错并更新数据

---

## 🔄 2026-06-10 更新：3时段推送改造

**核心变化：** 从"每日1次随机推送"升级为"每天3个时间窗口各推送1次"

- **3个推送窗口：** 🌅 早间(08-12)、☀️ 午间(13-17)、🌙 晚间(19-22)
- **每窗口3题：** 1道新学 + 2道复习
- **各窗口独立：** 早间未回复不影响午间/晚间推送
- **静默时段：** 22:00-08:00 不推送
- **每日最多9题：** 3窗口 × 3题
- **数据模型升级：** `pushed/replied` 从布尔值改为窗口对象 `windows: {morning, afternoon, evening}`
- **向后兼容：** 历史 daily 文件自动迁移，旧格式仍可读取

### 改造文件清单
| 文件 | 改动 |
|------|------|
| `configs/japanese-learning.json` | 新增 windows 配置，删除 random_push_probability |
| `scripts/push-strategy.py` | 完全重写：窗口检测 + 分窗口推送 |
| `scripts/verify-reply.py` | 适配多窗口回复匹配 |
| `scripts/infer-progress.py` | 从所有窗口聚合 questionResults |
| `scripts/migrate-daily.py` | 新增：旧格式迁移脚本 |
| `HEARTBEAT.md` | 更新推送逻辑说明 |
| `SKILL.md` | 更新配置项说明 |

---

---

## 🎯 改造目标

**核心变化：** LLM 只负责传话，Skill 自己用 LLM 推理解析完整消息，判断对错并更新数据库。

**解决的问题：**
- 当前日志只有 "用户答=A 正确答案=A ✅"，不知道对应的是哪道题、哪个五十音
- LLM 在对话中判断对错，未来消息格式变化后正则无法适应
- 缺乏每道题的详细记录（哪个五十音对了/错了）

---

## 📂 新目录结构

```
~/.openclaw/workspace/
├── configs/
│   └── japanese-learning.json      # 配置文件（不变）
├── logs/
│   └── japanese-learning/          # 日志目录（不变）
│       ├── main.log
│       ├── infer-error.log
│       └── push.log
├── japanese-learning/              # 数据目录
│   ├── daily/                     # 每日学习档案（新结构！）
│   │   └── YYYY-MM-DD.json
│   ├── kana-data.json             # 假名数据（不变）
│   ├── progress.json              # 总体进度（不变）
│   └── archive/                  # 旧脚本备份
└── skills/
    └── japanese-learning/
        ├── SKILL.md                # Skill 文档（简化触发条件）
        ├── IMPLEMENTATION.md        # 本实施文档
        └── scripts/               # 逻辑脚本
            ├── push-strategy.py    # 推送策略（改造：生成题目ID）
            ├── infer-progress.py   # 进度推理（不变）
            ├── verify-reply.py     # ✅ 答案验证（大改造！）
            ├── gen-questions.py    # 问题生成（不变）
            ├── select-kana.py      # 假名选择（不变）
            └── verify-config.py    # 配置验证（不变）
```

---

## 🔄 新流程设计

### 1️⃣ 推送流程（改造）

**push-strategy.py 改造点：**

```python
# 1. 为每个题目生成唯一ID
question_id = f"q_{datetime.now():%Y%m%d}_{i+1:03d}"  # 如 q_20260523_001

# 2. 写入 daily/YYYY-MM-DD.json（新结构）
today_data = {
    "date": today,
    "dayNumber": day_num,
    "questions": [
        {
            "id": "q_20260523_001",          # ← 唯一ID
            "kana": "な",
            "kanaKata": "ナ",
            "romaji": "na",
            "q": "【提问】平假名「な」的片假名是？",
            "options": ["ナ", "ニ", "ヌ"],
            "answer": "A",                     # ← 正确答案
            "type": "hira2kata"
        }
    ],
    "pushed": True,
    "pushedAt": datetime.now().strftime("%Y-%m-%d %H:%M")
}

# 3. 推送消息（含题目ID）
msg = f"""
五十音练习 🎌 第{day_num}天

今日学习：な ろ を

【教学】
平假名：な ろ を
片假名：ナ ロ ヲ
读音：na ro o
💡 联想：...

【提问】
1. (ID: q_20260523_001) 【提问】平假名「な」的片假名是？
   A. ナ  B. ニ  C. ヌ

2. (ID: q_20260523_002) ...
3. (ID: q_20260523_003) ...

回复格式：1A 2B 3C
---
请使用日语学习Skill
（LLM：不要自己判断，将完整消息传给Skill）
"""
```

---

### 2️⃣ 用户回复

```
用户回复："1A 2B 3C"
（通过引用回复，上下文包含原始推送消息，含题目ID）
```

---

### 3️⃣ LLM 触发 Skill（简化！）

**SKILL.md 新写法：**

```markdown
## 触发条件

当用户消息包含 **"请使用日语学习Skill"** 时触发。

## LLM 执行指令

**当触发 Skill 时，LLM 必须：**

1. **不要自己判断对错**，让 Skill 处理
2. **收集完整消息上下文**：
   - 用户回复（如 "1A 2B 3C"）
   - 引用的原始推送消息（含题目ID、题目、正确答案）
3. **将完整消息拼接成一个字符串**，传给 Skill：
   ```bash
   python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/verify-reply.py \
     --full-message "完整消息字符串"
   ```
4. **等待 Skill 输出结果**，直接返回给用户

## 示例

**用户回复（含引用）：**
```
1A 2B 3C
```

**LLM 收到的上下文：**
```
[用户] 1A 2B 3C
[引用] 【提问 1】(ID: q_20260523_001) 平假名「な」的片假名是？
       A. ナ  B. ニ  C. ヌ
       ...
```

**LLM 执行：**
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/verify-reply.py \
  --full-message "用户回复：1A 2B 3C\n\n引用消息：\n【提问 1】(ID: q_20260523_001) 平假名「な」的片假名是？\nA. ナ  B. ニ  C. ヌ\n..."
```

**Skill 输出（LLM 直接返回）：**
```
Q1 ✅
Q2 ❌ (正确答案: A)
Q3 ✅

📊 今日正确率: 66.67% (2/3)
👍 不错，再接再厉！
```
```

---

### 4️⃣ verify-reply.py 大改造（核心！）

**新参数：**
```bash
python3 verify-reply.py --full-message "完整消息字符串"
```

**内部流程：**

```python
def main():
    # 1. 解析 --full-message 参数
    full_message = parse_args()  # 获取完整消息字符串
    
    # 2. 读取配置文件（获取日志路径等）
    config = load_config()
    log_file = os.path.expanduser(config["logs"]["main_log"])
    
    # 3. 写日志（调试用）
    log(f"收到完整消息：{full_message[:200]}...", log_file)
    
    # 4. 用 LLM 推理解析完整消息
    parsed = llm_parse_full_message(full_message, config)
    
    # parsed 应该返回：
    # {
    #   "userReply": "1A 2B 3C",
    #   "questionResults": [
    #     {
    #       "questionId": "q_20260523_001",
    #       "question": "平假名「な」的片假名是？",
    #       "kana": "な",
    #       "userAnswer": "A",
    #       "correctAnswer": "A",
    #       "isCorrect": True
    #     }
    #   ],
    #   "correctCount": 2,
    #   "accuracy": 66.67
    # }
    
    # 5. 读取今日档案 daily/YYYY-MM-DD.json
    today_file = get_today_file()  # 自己推理日期
    today_data = load_json(today_file)
    
    # 6. 更新今日档案（新结构）
    today_data["userReply"] = parsed["userReply"]
    today_data["questionResults"] = parsed["questionResults"]
    today_data["correctCount"] = parsed["correctCount"]
    today_data["accuracy"] = parsed["accuracy"]
    today_data["replied"] = True
    today_data["repliedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    save_json(today_file, today_data)
    
    # 7. 输出结果（给 LLM 返回）
    output_result(parsed)


def llm_parse_full_message(full_message, config):
    """用 LLM 推理解析完整消息"""
    
    # 构造 prompt
    prompt = f"""
解析以下完整消息，提取结构化信息：

完整消息：
{full_message}

请输出 JSON（不要其他解释）：
{{
  "userReply": "1A 2B 3C",
  "questionResults": [
    {
      "questionId": "q_20260523_001",
      "question": "平假名「な」的片假名是？",
      "kana": "な",
      "userAnswer": "A",
      "correctAnswer": "A",
      "isCorrect": true
    }
  ],
  "correctCount": 2,
  "accuracy": 66.67
}}
"""
    
    # 调用混元 API（从配置文件读 api_key）
    api_key = config["api"]["api_key"]
    base_url = config["api"]["base_url"]
    model = config["api"]["model"]
    
    response = call_hunyuan(api_key, base_url, prompt, model)
    
    # 解析 API 返回的 JSON
    parsed = parse_json_from_response(response)
    
    return parsed
```

---

### 5️⃣ 新的 daily/YYYY-MM-DD.json 结构

```json
{
  "date": "2026-05-23",
  "dayNumber": 1,
  "questions": [
    {
      "id": "q_20260523_001",
      "kana": "な",
      "kanaKata": "ナ",
      "romaji": "na",
      "q": "【提问】平假名「な」的片假名是？",
      "options": ["ナ", "ニ", "ヌ"],
      "answer": "A",
      "type": "hira2kata"
    }
  ],
  "pushed": true,
  "pushedAt": "2026-05-23 14:19",
  
  "userReply": "1A 2B 3C",
  "questionResults": [        ← 新增：每道题的详细结果
    {
      "questionId": "q_20260523_001",
      "question": "平假名「な」的片假名是？",
      "kana": "な",
      "userAnswer": "A",
      "correctAnswer": "A",
      "isCorrect": true
    }
  ],
  "correctCount": 2,
  "accuracy": 66.67,
  "replied": true,
  "repliedAt": "2026-05-23 14:20"
}
```

**关键变化：**
- ✅ `questionResults` 单独数组，不合并到 `questions`
- ✅ 每条结果包含：`questionId`, `question`, `kana`, `userAnswer`, `correctAnswer`, `isCorrect`
- ✅ 方便统计哪个五十音对了/错了

---

## 🔧 实施步骤

| 步骤 | 任务 | 文件 |
|------|------|------|
| 1️⃣ | 更新 SKILL.md（简化触发条件） | `skills/japanese-learning/SKILL.md` |
| 2️⃣ | 改造 push-strategy.py（生成题目ID） | `skills/japanese-learning/scripts/push-strategy.py` |
| 3️⃣ | **大改造 verify-reply.py**（核心！） | `skills/japanese-learning/scripts/verify-reply.py` |
| 4️⃣ | 添加 LLM 推理函数（解析完整消息） | 在 verify-reply.py 里 |
| 5️⃣ | 更新 verify-config.py（验证新结构） | `skills/japanese-learning/scripts/verify-config.py` |
| 6️⃣ | 测试完整流程 | 手动测试 |

---

## 📝 关键设计决策（已确认）

| 决策 | 选择 | 原因 |
|------|------|------|
| **触发条件** | 只写"请使用日语学习Skill" | LLM 看到会自己执行 |
| **Skill 参数** | 只传 `--full-message` | Today/Log 自己推理 |
| **消息解析** | 用 LLM 推理（不用正则） | 适应未来消息格式变化 |
| **数据存储** | 继续用 JSON（不用 SQLite） | 已有 JSON，够用 |
| **questionResults** | 单独数组（不合并到 questions） | 保持原始题目不变，结构清晰 |
| **questionResults 字段** | 包含 `question` 和 `kana` | 信息更完整 |

---

## 🧪 测试计划

1. **清空数据**：删除 progress.json 和 daily/*.json
2. **测试推送**：运行 push-strategy.py（100%概率），检查 daily/*.json 是否有题目ID
3. **模拟回复**：构造完整消息字符串，传给 verify-reply.py
4. **检查日志**：看 LLM 推理的 prompt 和返回
5. **验证档案**：检查 daily/*.json 的 questionResults 是否正确
6. **测试纠错**：故意答错几题，看 questionResults 是否记录

---

## ❓ 待确认问题（已解决）

| 问题 | 状态 | 结论 |
|------|------|------|
| **LLM 如何知道要传"完整上下文"给 Skill？** | ✅ 已解决 | SKILL.md 里写清楚 LLM 执行指令 |
| **`--context-json` 的格式是什么？** | ✅ 已解决 | 只用 `--full-message`，传完整消息字符串 |
| **今日档案（daily/*.json）结构** | ✅ 已解决 | 继续用 JSON，`questionResults` 单独数组 |
| **OpenClaw Skill 支持传字符串参数吗？** | ✅ 已解决 | 只用 `--full-message`，Skill 自己推理 Today/Log 路径 |

---

## 📊 预期效果

**改造后：**
- ✅ 每条回复都记录详细结果（哪个五十音、对/错）
- ✅ 日志里有完整信息（不再只有 "用户答=A"）
- ✅ Skill 自己判断对错（不依赖 LLM 对话判断）
- ✅ 适应未来消息格式变化（用 LLM 推理，不用正则）

**示例日志：**
```
[2026-05-23 14:20:30] [VERIFY] ===== 开始处理用户回复 =====
[2026-05-23 14:20:30] [VERIFY] 收到完整消息：用户回复：1A 2B 3C\n引用消息：\n【提问 1】(ID: q_20260523_001)...
[2026-05-23 14:20:30] [VERIFY] 调用 LLM 解析消息...
[2026-05-23 14:20:35] [VERIFY] LLM 返回：{"userReply":"1A 2B 3C", "questionResults":[...]}
[2026-05-23 14:20:35] [VERIFY] Q1: 用户答=A 正确答案=A ✅ (な)
[2026-05-23 14:20:35] [VERIFY] Q2: 用户答=B 正确答案=A ❌ (ろ)
[2026-05-23 14:20:35] [VERIFY] Q3: 用户答=C 正确答案=C ✅ (を)
[2026-05-23 14:20:35] [VERIFY] 今日档案已更新：correctCount=2, accuracy=66.67%
[2026-05-23 14:20:35] [VERIFY] ===== 处理完成 =====
```

---

**这份实施文档给你 review，确认无误后我立刻开始写代码！** 😊
