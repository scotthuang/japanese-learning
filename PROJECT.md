# 日语五十音学习系统 - 项目文档

> 创建时间：2026-05-23
> 作者：Shadow 🦊
> 用户：Scott

---

## 📋 项目概述

一套完整的日语五十音（假名）学习系统，集成在 OpenClaw 中，支持：
- ✅ 自动推送练习（心跳触发）
- ✅ 答案验证与反馈
- ✅ 每日学习沉淀（分析历史、生成档案）
- ✅ 个性化学习方案（新学 + 复习混合）
- ✅ 日语单词联想记忆

---

## 📂 文件结构

```
~/.openclaw/workspace/
├── japanese-learning/                 # 数据目录
│   ├── kana-data.json              # 46 个假名基础数据（含日语单词）
│   ├── progress.json               # 总体进度（已掌握列表、正确率、趋势）
│   ├── learning-profile.md         # 个人学习档案（Markdown，人类可读）
│   ├── next-day-plan.json         # 第二天学习方案（JSON，程序可读）
│   ├── daily/                     # 每日学习档案
│   │   └── YYYY-MM-DD.json
│   └── logs/                     # 日志（实际在 workspace/logs/）
│
├── skills/japanese-learning/scripts/  # 脚本目录
│   ├── push-strategy.py         # 推送脚本（3 新学 + 2 复习）
│   ├── verify-reply.py          # 答案验证（LLM 解析）
│   ├── infer-progress.py        # 每日沉淀（分析历史、生成档案）
│   ├── gen-questions.py        # 题目生成
│   └── select-kana.py         # 假名选择
│
├── configs/
│   └── japanese-learning.json  # 配置文件（路径、API、推送参数）
│
└── logs/
    └── japanese-learning/
        ├── main.log                # 主日志
        ├── infer-error.log         # 推理错误日志
        └── push.log                # 推送日志
```

---

## 🔄 核心流程

### 一、推送流程（心跳触发）

```
每 30 分钟心跳（30% 概率）
        ↓
push-strategy.py 执行
        ↓
读取 next-day-plan.json（第二天方案）
        ↓
选择假名：
  - 新学：3 个（从方案推荐）
  - 复习：2 个（从易错列表）
        ↓
生成推送消息：
  【教学】3 个新学假名 + 日语单词
  【提问】5 道题（3 新 + 2 复习）
        ↓
推送到微信（openclaw-weixin）
```

**推送消息格式：**
```
五十音练习 🎌 第X天

【教学】
平假名：ひ り ら
片假名：ヒ リ ラ
读音：hi ri ra
💡 单词：ひと（人）| りんご（苹果）| らいねん（明年）

【提问】
1. (ID: q_...) 读音「hi」对应的片假名是？
   A. コ  B. ホ  C. ヒ
2. (ID: q_...) 读音「ri」对应的片假名是？
   A. ト  B. ツ  C. リ
3. (ID: q_...) 读音「ra」对应的片假名是？
   A. モ  B. ラ  C. キ
4. (ID: q_...) 平假名「う」的片假名是？ [复习]
   A. ウ  B. イ  C. エ
5. (ID: q_...) 读音「tsu」对应的平假名是？ [复习]
   A. つ  B. く  C. す

回复格式：1A 2B 3C 4D 5E
---
请使用日语学习Skill
```

---

### 二、答案验证流程

```
用户回复：「1C 2C 3B 4A 5B
           请使用日语学习Skill」
        ↓
japanese-learning Skill 触发
        ↓
verify-reply.py 执行（--full-message 参数）
        ↓
LLM 解析完整消息（提取答案、匹配题目ID）
        ↓
更新 daily/YYYY-MM-DD.json：
  - userReply: "1C 2C 3B 4A 5B"
  - questionResults: 每道题的对错
  - correctCount: 正确数
  - accuracy: 正确率
  - replied: true
        ↓
更新 progress.json：
  - mastered: 添加新掌握的假名
  - masteredCount: 更新计数
        ↓
反馈到微信：
  - 🎉 全对！太棒了！
  - 👍 不错，再接再厉！
  - 💪 继续加油，多复习几遍！
```

---

### 三、每日沉淀流程（凌晨 1:30 cron）

```
每天 01:30（Asia/Shanghai）
        ↓
cron 任务：日语学习每日沉淀
        ↓
infer-progress.py 执行
        ↓
1. 分析所有 daily/*.json：
   - 统计每个假名的答题次数、正确次数
   - 计算正确率
   - 判断掌握度（≥80% = 掌握，<60% = 易错）
        ↓
2. 生成 learning-profile.md（个人学习档案）
   - 总体情况（天数、掌握数、正确率、趋势）
   - 掌握度分布（每行统计）
   - 已掌握假名列表
   - 易错假名列表
   - 各假名详细统计
   - 学习历史
   - 第二天学习方案
        ↓
3. 生成 next-day-plan.json（第二天方案）
   {
     "date": "2026-05-24",
     "generatedAt": "2026-05-23 20:07",
     "newKana": ["あ", "い", "う"],
     "reviewKana": [],
     "suggestedRow": "あ行",
     "quizPlan": {
       "newCount": 3,
       "reviewCount": 2,
       "newKanaForQuiz": ["あ", "い", "う"],
       "reviewKanaForQuiz": [],
       "note": "从あ行选3个新学；从易错列表选2个复习"
     }
   }
        ↓
4. 更新 progress.json（nextDayPlan 字段）
        ↓
推送通知到微信：「✅ 每日沉淀完成！已更新学习档案和第二天的学习方案。」
```

---

## 🎯 核心功能详解

### 1️⃣ 知识卡片（教学部分）

- **每次推送 3 个新学假名**
- 显示内容：
  - 平假名：ひ り ら
  - 片假名：ヒ リ ラ
  - 读音：hi ri ra
  - **💡 单词**：ひと（人）| りんご（苹果）| らいねん（明年）

**日语单词示例（kana-data.json）：**
| 假名 | 片假名 | 读音 | 日语单词 |
|------|--------|------|----------|
| あ | ア | a | アパート（公寓）|
| い | イ | i | いぬ（狗）|
| う | ウ | u | うえ（上）|
| か | カ | ka | かさ（伞）|
| き | キ | ki | きく（菊花）|

---

### 2️⃣ 混合出题（提问部分）

- **总共 5 道题**：3 道新学 + 2 道复习
- **知识卡片只显示新学的 3 个假名**
- **复习题不出现在卡片里**，只出题
- **题型随机**：
  - 平假名 → 片假名
  - 片假名 → 平假名
  - 读音 → 平假名
  - 读音 → 片假名

**回复格式：** `1A 2B 3C 4D 5E`（5 个答案）

---

### 3️⃣ 个人学习档案（learning-profile.md）

**自动生成，包含：**

#### 📊 总体情况
| 项目 | 数值 |
|------|------|
| 已学天数 | X 天 |
| 已掌握假名 | X / 46 |
| 总体正确率 | X% |
| 学习趋势 | improving / stable / declining |

#### 掌握度分布
| 行 | 总数 | 已掌握 | 正确率 | 状态 |
|----|------|--------|--------|------|
| あ行 | 5 | 3 | 90% | ✅ 学习中 |
| か行 | 5 | 0 | 0% | ❌ 未学 |

#### 假名掌握详情
- **✅ 已掌握**（≥80%）
- **⚠️ 易错假名**（<60%）
- **📝 各假名统计**（答题次数、正确率）

#### 学习历史
| 日期 | 天数 | 学习假名 | 正确率 | 新学 | 复习 |
|------|------|----------|--------|------|------|
| 2026-05-23 | 第1天 | ひ り ら | 100% | 3 | 0 |

#### 🎲 第二天学习方案
- **新学建议**：推荐学习哪一行（如 あ行）
- **巩固建议**：需要复习的假名
- **出题意向**：具体到假名，供推送脚本读取

---

### 4️⃣ 第二天学习方案（next-day-plan.json）

**JSON 格式，方便程序读取：**

```json
{
  "date": "2026-05-24",
  "generatedAt": "2026-05-23 20:07",
  "newKana": ["あ", "い", "う"],
  "reviewKana": [],
  "suggestedRow": "あ行",
  "quizPlan": {
    "newCount": 3,
    "reviewCount": 2,
    "newKanaForQuiz": ["あ", "い", "う"],
    "reviewKanaForQuiz": [],
    "note": "从あ行选3个新学；从易错列表选2个复习"
  }
}
```

**push-strategy.py 读取此文件出题。**

---

## ⏰ 时间计划

| 时间 | 任务 | 说明 |
|------|------|------|
| **每 30 分钟** | 心跳检查 | 30% 概率推送五十音练习（3 新 + 2 复习） |
| **每天 01:30** | 每日沉淀 | 分析历史、更新 learning-profile.md 和 next-day-plan.json |
| **用户回复时** | 答案验证 | verify-reply.py 更新 daily/*.json 和 progress.json |

---

## 🛠️ 配置文件

### configs/japanese-learning.json

```json
{
  "workspace": {
    "root": "~/.openclaw/workspace/japanese-learning",
    "progress_file": "~/.openclaw/workspace/japanese-learning/progress.json",
    "daily_dir": "~/.openclaw/workspace/japanese-learning/daily",
    "kana_data": "~/.openclaw/workspace/japanese-learning/kana-data.json"
  },
  "logs": {
    "dir": "~/.openclaw/workspace/logs/japanese-learning",
    "main_log": "~/.openclaw/workspace/logs/japanese-learning/main.log",
    "push_log": "~/.openclaw/workspace/logs/japanese-learning/push.log",
    "infer_error_log": "~/.openclaw/workspace/japanese-learning/infer-error.log"
  },
  "api": {
    "api_key": "从 openclaw.json 读取",
    "base_url": "https://api.lkeap.cloud.tencent.com/plan/v3",
    "model": "hy3-preview"
  },
  "push_strategy": {
    "interval_seconds": 7200,
    "random_push_probability": 30,
    "questions_per_day": 5
  },
  "wechat": {
    "channel": "openclaw-weixin",
    "target": "o9cq806Y9QtMkjTEauM8nYFvJTL8@im.wechat"
  },
  "paths": {
    "openclaw_bin": "/usr/local/bin/openclaw"
  },
  "script_settings": {
    "timeout_seconds": 30
  }
}
```

---

## 📊 数据流转图

```
┌─────────────────┐
│  凌晨 1:30（cron）                                 │
│  infer-progress.py 执行：                          │
│  1. 分析所有 daily/*.json（答题详情）               │
│  2. 统计每个假名的掌握度（正确率）                  │
│  3. 生成 learning-profile.md（学习档案）           │
│  4. 生成 next-day-plan.json（第二天方案）          │
│  5. 推送微信通知：「✅ 每日沉淀完成！」            │
└───────────────────┘
                     ↓
┌─────────────────┐
│  心跳每 30 分钟（30% 概率）                      │
│  push-strategy.py 执行：                          │
│  1. 读取 next-day-plan.json（第二天方案）          │
│  2. 新学题：从方案推荐选 3 个假名                │
│  3. 复习题：从易错列表选 2 个假名                │
│  4. 生成题目（混合：平假名↔片假名↔读音）          │
│  5. 推送微信：                                   │
│     【教学】3 个新学假名 + 日语单词               │
│     【提问】5 道题（3 新 + 2 复习）             │
└───────────────────┘
                     ↓
┌─────────────────┐
│  用户收到推送，回复：「1A 2B 3C 4D 5E」           │
│  + 「请使用日语学习Skill」                        │
└───────────────────┘
                     ↓
┌─────────────────┐
│  verify-reply.py 执行（Skill 触发）：               │
│  1. 用 LLM 解析用户的完整回复                     │
│  2. 验证每道题的答案                            │
│  3. 更新 daily/YYYY-MM-DD.json（correctCount）    │
│  4. 更新 progress.json（mastered 列表）            │
│  5. 反馈：「🎉 全对！太棒了！」                 │
└───────────────────┘
                     ↓
            （回到心跳等待下次推送）
```

---

## 🎉 当前状态（2026-05-23）

- ✅ 已掌握：**ひ、り、ら**（3/46，100% 正确率）
- ✅ 第二天方案：推荐学 **あ行**（あ、い、う、え、お）
- ✅ 下次推送：约 30 分钟内（心跳触发）
- ✅ 定时任务：每天 01:30 自动沉淀

---

## 🚀 扩展方向（未来）

- [ ] 增加片假名单词（如 アイスクリーム「冰淇淋」）
- [ ] 支持浊音、半浊音、拗音
- [ ] 语音朗读假名（调用 TTS）
- [ ] 生成学习报告图片（可视化进度）
- [ ] 支持多用户（家庭成员：Season、Wandy）

---

## 📝 更新日志

### 2026-05-23
- ✅ 完成五十音学习系统基础架构
- ✅ 实现混合出题（3 新学 + 2 复习）
- ✅ 添加日语单词联想记忆
- ✅ 实现每日沉淀（分析历史、生成档案）
- ✅ 创建第二天学习方案（JSON）
- ✅ 配置 cron 定时任务（凌晨 1:30）
- ✅ 完善推送脚本（读取方案出题）
- ✅ 生成项目文档（PROJECT.md）

---

*此文档由 Shadow 🦊 自动生成，最后更新：2026-05-23 20:15*
