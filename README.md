# 日语五十音学习 Skill

> 作者：Shadow 🦊
> 创建时间：2026-05-23
> 用户：Scott

---

## 📋 概述

一套完整的日语五十音（假名）学习系统，集成在 OpenClaw 中，支持自动推送、答案验证、每日沉淀、个性化学习方案。

---

## ✨ 核心功能

### 1️⃣ 自动推送（心跳触发）
- 每 30 分钟心跳检查，30% 概率推送
- 每次推送 **5 道题**（3 道新学 + 2 道复习）
- 知识卡片：**3 个新学假名** + **日语单词**（如 あ→アパート「公寓」）

### 2️⃣ 混合出题
- 新学题：对应卡片上的假名
- 复习题：从已掌握列表出题，**不显示在卡片里**
- 题型随机：平假名↔片假名↔读音

### 3️⃣ 答案验证
- 使用 LLM（混元 API）解析用户回复
- 自动验证答案、更新每日档案
- 即时反馈：🎉 全对！/ 💪 继续加油

### 4️⃣ 每日沉淀（凌晨 1:30 cron）
- 分析所有历史答题详情
- 生成 `learning-profile.md`（个人学习档案）
- 生成 `next-day-plan.json`（第二天学习方案）
- 自动推送完成通知

### 5️⃣ 个性化学习方案
- **第二天方案**：推荐新学哪些行、巩固哪些假名
- `push-strategy.py` 直接读取方案出题
- 精准复习：根据正确率推荐易错假名

---

## 📂 文件结构

```
japanese-learning/
├── SKILL.md              # Skill 文档（触发条件、执行流程）
├── PROJECT.md            # 项目文档（完整流程、配置说明）
├── IMPLEMENTATION.md    # 实现总结（重构记录）
├── README.md            # 本文件
├── .gitignore           # Git 忽略规则
├── scripts/            # 脚本目录
│   ├── push-strategy.py      # 推送脚本（3 新学 + 2 复习）
│   ├── verify-reply.py       # 答案验证（LLM 解析）
│   ├── infer-progress.py     # 每日沉淀（分析历史、生成档案）
│   ├── gen-questions.py     # 题目生成
│   └── select-kana.py      # 假名选择
└── (数据文件在 workspace/japanese-learning/)
    ├── kana-data.json         # 46 个假名数据（含日语单词）
    ├── progress.json          # 总体进度
    ├── learning-profile.md    # 个人学习档案
    ├── next-day-plan.json    # 第二天方案
    └── daily/                # 每日学习档案
        └── YYYY-MM-DD.json
```

---

## 🚀 快速开始

### 1. 安装
将 `japanese-learning` 目录放到 `~/.openclaw/workspace/skills/` 下。

### 2. 配置
编辑 `~/.openclaw/workspace/configs/japanese-learning.json`，配置：
- API Key（混元 API）
- 微信推送参数（channel、target）
- 推送策略（概率、冷却时间）

### 3. 测试推送
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/push-strategy.py
```

### 4. 测试验证
回复消息：「1A 2B 3C 4D 5E\n请使用日语学习Skill」

### 5. 查看档案
```bash
cat ~/.openclaw/workspace/japanese-learning/learning-profile.md
```

---

## 📅 定时任务

| 时间 | 任务 | 说明 |
|------|------|------|
| **每 30 分钟** | 心跳检查 | 30% 概率推送五十音练习 |
| **每天 01:30** | 每日沉淀 | 分析历史、更新学习档案、生成第二天方案 |

---

## 🔄 数据流转

```
用户回复
   ↓
verify-reply.py（验证，更新 daily/*.json）
   ↓
（凌晨 1:30 自动触发）
infer-progress.py（分析历史）
   ↓
生成 learning-profile.md + next-day-plan.json
   ↓
（下次心跳）
push-strategy.py 读取方案
   ↓
推送新题目（按方案出题）
```

---

## 🎯 当前状态（2026-05-23）

- ✅ 已掌握：**ひ、り、ら**（3/46，100% 正确率）
- ✅ 第二天方案：推荐学 **あ行**（あ、い、う、え、お）
- ✅ Git 仓库：已初始化，master 分支

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
- ✅ 初始化 Git 仓库

---

*此文档由 Shadow 🦊 维护，最后更新：2026-05-23 20:20*
