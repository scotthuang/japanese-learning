---
name: japanese-learning
description: 日语五十音学习系统。当用户回复五十音练习答案（格式如"1A 2B 3C"），或消息包含"请使用日语学习Skill"时触发。Skill 自己用 LLM 推理解析完整消息，判断对错并更新数据。
---

# 日语学习 Skill

处理用户回复、自己判断对错、更新档案、返回结果。

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
            ├── verify-reply.py     # ✅ 答案验证（大改造！用LLM推理）
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
2. **收集完整消息上下文**：
   - 用户回复（如 "1A 2B 3C"）
   - 引用的原始推送消息（含题目ID、题目、正确答案）
3. **将完整消息拼接成一个字符串**，传给 Skill：
   ```bash
   python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/verify-reply.py \
     --full-message "完整消息字符串"
   ```
4. **等待 Skill 输出结果**，直接返回给用户，不要自己生成回复！

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

**参数：** 只接收 `--full-message "完整消息字符串"`

**内部流程：**
1. 解析 `--full-message` 参数，获取完整消息
2. 读取配置文件（获取 API key、日志路径）
3. 调用混元 API（用 LLM 推理）解析完整消息
   - Prompt 要求返回结构化 JSON（含 questionResults）
4. 读取今日档案 `daily/YYYY-MM-DD.json`
5. 更新今日档案：
   - `userReply`: 用户回复
   - `questionResults`: 每道题的详细结果（题目、五十音、对错）
   - `correctCount`, `accuracy`, `replied=true`
6. 输出结果给 LLM（Q1 ✅ Q2 ❌... 格式）

**完整消息字符串格式：**
```
用户回复：1A 2B 3C

引用消息：
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

---

## 推送消息格式（已更新）

```
五十音练习 🎌 第1天

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

回复格式：1A 2B 3C
---
请使用日语学习Skill
```

**注意：** 末尾只写"请使用日语学习Skill"，不带其他说明！

---

## 注意事项

### 学习模式
- ✅ LLM **只负责传话**，不判断对错
- ✅ Skill（verify-reply.py）**自己用 LLM 推理**解析消息
- ✅ 不用正则，用 LLM 推理适应未来消息格式变化
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
| `api.model` | 使用的混元模型 | `hy3-preview` |
| `api.api_key` | API key（已配置） | `***` |
| `push_strategy.interval_seconds` | 推送间隔（秒） | `7200`（2小时） |
| `push_strategy.random_push_probability` | 随机推送概率（%） | `30` |
| `push_strategy.questions_per_day` | 每日题目数 | `3` |
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
- ✅ verify-reply.py 大改造（用 LLM 推理）
- ✅ 今日档案新增 questionResults
- ✅ LLM 只传话，不判断对错
