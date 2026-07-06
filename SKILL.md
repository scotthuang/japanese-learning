---
name: japanese-learning
description: 日语学习系统。当用户回复练习答案（格式如"1A 2B 3C 4D"），或消息包含"请使用日语学习Skill"时触发。系统支持五十音题和单词识读题，并更新 daily/progress 数据。
---

# 日语学习 Skill

处理用户回复、判断对错、更新档案、返回结果。46 个基础假名完成后，推送自动进入 v3.0 单词模式：白天先学新词，晚间集中测验 recall。

## 目录结构

```
~/.openclaw/workspace/
├── configs/
│   └── japanese-learning.json      # 配置文件（含 API key）
├── logs/
│   └── japanese-learning/          # 日语学习日志目录
│       ├── main.log                # 主日志
│       ├── infer-error.log         # 推理错误日志
│       ├── push.log                # 推送日志
│       └── script.log              # 脚本日志
├── japanese-learning/              # 数据目录
│   ├── daily/                     # 每日学习档案（含题目ID）
│   ├── kana-data.json             # 假名数据
│   ├── progress.json              # 总体进度
│   └── archive/                  # 旧脚本备份
└── skills/
    └── japanese-learning/
        ├── SKILL.md                # 本文档
        ├── IMPLEMENTATION.md       # 实施文档
        └── scripts/               # 逻辑脚本
            ├── push-strategy.py    # 推送策略（生成题目ID）
            ├── infer-progress.py   # 进度推理
            ├── verify-reply.py     # 答案验证（确定性解析 + 旧 LLM 兼容）
            ├── gen-word-questions.py # 单词学习/测验生成
            ├── gen-questions.py    # 问题生成
            ├── select-kana.py      # 假名选择
            ├── verify-config.py    # 配置验证
            └── review-mastered.py  # 复习已掌握的假名
```

## 触发条件

1. **学习模式**：当用户消息包含 **"请使用日语学习Skill"** 时触发
2. **复习模式**：当用户消息包含 **"复习五十音"**、**"查看已学"**、**"复习假名"** 时触发
3. **五十音图查询**：当用户消息包含 **"查看五十音图"**、**"五十音表"**、**"五十音"** 时触发

## LLM 执行指令（重要！）

**当触发 Skill 时，LLM 必须：**

1. **不要自己判断对错**，让 Skill 处理
2. **分离收集两个独立的上下文**：
   - `--user-reply`：用户回复的答案字符串（如 `"1A 2B 3C"`），**只包含用户的答案，不要掺入正确答案！**
   - `--full-message`：引用的原始推送消息（含题目ID、题目、选项，用于匹配上下文）
3. **用双参数方式调用 Skill**（推荐）：
   ```bash
   python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/verify-reply.py \
     --user-reply "1A 2B 3C 4D" \
     --full-message "引用推送消息..."
   ```
   > **重要**：`--user-reply` 只传用户的实际答案（如 `1C 2B 3B 4D`），
   > 不要把引用消息中的正确答案误填进去！Skill 脚本自己有题目和正确答案数据，
   > 会自动判断对错，你只需如实传递用户输入即可。
4. **等待 Skill 输出结果**，直接返回给用户，不要自己生成回复！
5. **向后兼容**：如果无法分离，也可以只传 `--full-message`（旧方式仍然可用）。

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

**LLM 执行（推荐的双参数方式）：**
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/verify-reply.py \
  --user-reply "1A 2B 3C" \
  --full-message "【提问 1】(ID: q_20260523_001) 平假名「な」的片假名是？
A. ナ  B. ニ  C. ヌ
..."
```
> 💡 **关键**：`--user-reply` 只传用户的答案 `1A 2B 3C`，引用消息传 `--full-message`。
> 脚本内部有正确答案，会自动判断对错，你（LLM）不需要也不应该把正确答案写到 --user-reply 里。

**旧方式（向后兼容，不推荐）：**
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/verify-reply.py \
  --full-message "用户回复：1A 2B 3C\n\n引用消息：\n【提问 1】(ID: q_20260523_001) ..."
```

**Skill 输出（LLM 直接返回）：**
```
Q1 ✅
Q2 ❌ (正确答案: A)
Q3 ✅

📊 本次正确率: 75.00% (3/4)
👍 不错，再接再厉！
```

---

## 复习功能

### 使用方式

用户可以说：
- "复习五十音"
- "查看已学的假名"
- "复习假名"
- "我学了哪些五十音"

### 复习模式

**1. 列表模式（默认）**
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/review-mastered.py list
```
显示所有已掌握的假名，按行分组。

**2. 测验模式**
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/review-mastered.py quiz
```
随机抽查已掌握的假名，显示假名让用户回忆罗马音和助记。

**3. 随机模式**
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/review-mastered.py random
```
随机显示一个已掌握的假名，包含完整信息。

**4. 按行筛选**
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/review-mastered.py list "は行"
```
只显示某个行的已掌握假名。

### LLM 执行指令（复习）

**当触发复习时，LLM 必须：**

1. **判断复习模式**（从用户消息中提取）：
   - 默认 → `list` 模式
   - "测验"、"测试" → `quiz` 模式
   - "随机" → `random` 模式
   - 指定行名 → `list "行名"`

2. **执行复习脚本**：
   ```bash
   python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/review-mastered.py <mode>
   ```

3. **直接返回脚本输出**，不要自己生成内容！

### 示例

**用户消息：**
```
复习五十音
```

**LLM 执行：**
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/review-mastered.py list
```

**返回给用户：**
```
📖 已掌握的假名（共 6 个）

【は行】
 ひ (ヒ) - hi  ひら（火）
 り (リ) - ri りんご（苹果）

【ら行】
 ら (ラ) - ra らくだ（骆驼）

📊 统计：
   总掌握：6 个
   准确率：100%
```

**用户消息：**
```
测验一下我学的五十音
```

**LLM 执行：**
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/review-mastered.py quiz
```

**返回给用户：**
```
📝 五十音复习测验（已掌握 6 个）

Q1: ひ (ヒ)
   回忆：罗马音 + 助记 = ?

Q2: り (リ)
   回忆：罗马音 + 助记 = ?

💡 答案：
A1: hi - ひら（火）
A2: ri - りんご（苹果）
```

---

## 脚本调用方式

### verify-reply.py（核心！）

**参数：**
- `--user-reply`（推荐，可选）：用户回复的答案字符串（如 `"1A 2B 3C 4D"`）
- `--full-message`（可选）：引用推送消息上下文（题目、选项等）
- 至少需要提供其中一个；推荐两个都传，分离用户答案和引用上下文

**推荐调用方式（双参数）：**
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/verify-reply.py \
  --user-reply "1A 2B 3C 4D" \
  --full-message "【提问 1】(ID: q_20260523_001) ..."
```

**旧调用方式（向后兼容，单参数）：**
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/verify-reply.py \
  --full-message "用户回复：1A 2B 3C\n\n引用消息：\n..."
```

**内部流程：**
1. 解析 `--user-reply`（如有）提取用户答案，解析 `--full-message`（如有）获取上下文
2. 读取配置文件（获取 API key、日志路径）
3. 如果提供了 `--user-reply`，脚本直接根据 daily 中保存的题目判分
   - 如果只有 `--full-message`，才调用 DeepSeek 兼容 API 解析完整消息（向后兼容）
   - Prompt 要求返回结构化 JSON（含 questionResults）
4. 读取目标档案 `daily/YYYY-MM-DD.json`
5. 更新档案中对应窗口的数据：
   - `userReply`: 用户回复
   - `questionResults`: 每道题的详细结果（题目、五十音/单词、对错）
   - `correctCount`, `accuracy`, `replied=true`
6. 输出结果给 LLM（Q1 ✅ Q2 ❌... 格式）

**`--user-reply` 字符串格式：**
```
1A 2B 3C 4D
```
支持空格分隔或连写（如 `1A2B3C4D`），答案字母支持 A/B/C/D（大小写均可）。

**`--full-message` 字符串格式（作为引用上下文）：**
```
【提问 1】(ID: q_20260523_001) 平假名「な」的片假名是？
A. ナ  B. ニ  C. ヌ

【提问 2】(ID: q_20260523_002) ...
```

**LLM 推理期望返回的 JSON：**
```json
{
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
}
```

---

## daily/YYYY-MM-DD.json 新结构

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
  "accuracy": 66.67,
  "replied": true,
  "repliedAt": "2026-05-23 14:20"
}
```

**关键变化：**
- ✅ `questions` 数组包含题目ID、kana、answer
- ✅ 新增 `questionResults` 数组，记录每道题详细结果
- ✅ 方便统计哪个五十音对了/错了
- ✅ v3.0 单词测验使用 `type: "word-exam"`，并记录 `word`、`correctKana`、`wrongKana`、`selectedRomaji`

---

## 单词模式推送格式（v3.0 先学后考）

### 白天学习推送

白天 3 个窗口（早间、午后、晚间）只展示新词，不出题：

```
📖 午后学习 🎌 第X天

今日新词：
おかね (オカネ) = okane 💴 钱
らく (ラク) = raku 😌 轻松

---
请使用日语学习Skill
```

学习窗口写入 daily 的对应 `windows.<window>`：
- `type: "study"`
- `mode: "word-study"`
- `studyWords`: 本窗口学习的 2 个新词
- `questions`: 空数组

### 晚间测验推送

22:00 后从当天 3 次学习记录中取 6 个新词，再混入 1 个复习词和 0-1 个错题词：

```
🎯 今日总结测验 🎌 第X天

【提问】
1. (ID: w_20260707_exam_001) 「ねこ」怎么读？
   A. neko 🐱 猫
   B. niku 🥩 肉
   C. neko 🐱 猫
   D. kumo ☁️ 云

回复格式：1A 2B 3C 4D 5A 6B 7C
---
请使用日语学习Skill
```

**注意：**
- 考试题保存为 `type: "word-exam"`
- 部分题目用片假名提问，训练片假名识读
- 选项优先来自 `word-data.json` 的 `similarGroup`
- 学习推送没有题目，不需要调用 `verify-reply.py`
- 末尾只写"请使用日语学习Skill"，不带其他说明

---

## 注意事项

### 学习模式
- ✅ LLM **只负责传话**，不判断对错
- ✅ Skill（verify-reply.py）在提供 `--user-reply` 时确定性判分
- ✅ 旧式完整消息仍可回退到 DeepSeek 解析
- ✅ 今日档案包含 `questionResults`，记录详细结果
- ✅ 日志路径从配置文件读取，Skill 自己推理今日档案路径

### 复习模式
- ✅ LLM **只负责执行脚本**，直接返回输出
- ✅ 支持三种模式：list（列表）、quiz（测验）、random（随机）
- ✅ 可以按行筛选，如 `list "は行"`
- ✅ 测验模式显示假名，让用户回忆，再揭晓答案

---

## 配置文件说明

所有可配置项都在 `~/.openclaw/workspace/configs/japanese-learning.json` 中。

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `workspace.root` | 日语学习数据根目录 | `~/.openclaw/workspace/japanese-learning` |
| `logs.dir` | 日志根目录 | `~/.openclaw/workspace/logs/japanese-learning` |
| `logs.main_log` | 主日志文件路径 | `~/.openclaw/workspace/logs/japanese-learning/main.log` |
| `workspace.word_data` | 单词库路径 | `~/.openclaw/workspace/japanese-learning/word-data.json` |
| `api.model` | 使用的 DeepSeek 模型 | `deepseek-chat` |
| `api.api_key` | API key（已配置） | `***` |
| `push_strategy.interval_seconds` | 心跳间隔（秒） | `1800`（30分钟） |
| `push_strategy.questions_per_window` | 每窗口题目数 | `4` |
| `push_strategy.new_per_window` | 每窗口新学数 | `1` |
| `push_strategy.review_per_window` | 每窗口复习数 | `2` |
| `push_strategy.word_new_per_window` | 单词模式每窗口新词数 | `2` |
| `push_strategy.word_review_per_window` | 学习窗口旧词数 | `0` |
| `push_strategy.word_wrong_per_window` | 学习窗口错题词数 | `0` |
| `push_strategy.word_exam_new` | 晚间测验新词数 | `6` |
| `push_strategy.word_exam_review` | 晚间测验复习词数 | `1` |
| `push_strategy.word_exam_wrong` | 晚间测验错题词数 | `1` |
| `push_strategy.windows.morning` | 早间学习窗口(08-11) | `🌅 早间学习` |
| `push_strategy.windows.afternoon` | 午后学习窗口(13-16) | `☀️ 午后学习` |
| `push_strategy.windows.evening` | 晚间学习窗口(19-21) | `🌙 晚间学习` |
| `push_strategy.windows.exam` | 晚间测验窗口(22-23) | `🎯 晚间测验` |
| `push_strategy.silent_start` | 静默开始时间 | `0` |
| `push_strategy.silent_end` | 静默结束时间 | `8` |
| `wechat.channel` | 微信推送渠道 | `openclaw-weixin` |

**修改配置后，脚本会自动读取新配置，无需重启。**

---

## 验证配置

```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/verify-config.py
```

---

**改造完成！** 🎉  
- ✅ 推送生成题目ID
- ✅ SKILL.md 简化触发条件
- ✅ verify-reply.py 支持确定性判分和旧式 LLM 解析
- ✅ 今日档案新增 questionResults
- ✅ LLM 只传话，不判断对错

---
## 测试行
这是 Claude Code 写入测试，时间：2026-05-30 02:30
