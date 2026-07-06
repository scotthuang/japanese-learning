# 日语学习 Skill

> 作者：Shadow 🦊
> 创建时间：2026-05-23
> 用户：Scott

---

## 概述

一套集成在 OpenClaw 中的日语学习系统。当前为 v3.0「先学后考」：46 个基础假名完成后，白天推送新词教学，晚间统一做单词 recall 测验。

---

## 核心功能

### 1. 自动推送
- 每 30 分钟心跳检查当前时间窗口
- 每天 4 个窗口：早间学习、午后学习、晚间学习、晚间测验
- 五十音完成前：假名题
- 五十音完成后：白天 3 次各学 2 个新词，不出题；22 点后测 6 个新词 + 复习/错题

### 2. 单词先学后考
- 学习推送保存为 `type: "study"` / `mode: "word-study"`，只记录 `studyWords`
- 测验题保存为 `type: "word-exam"`，题目 ID 为 `w_YYYYMMDD_exam_001`
- 题目随机使用平假名或片假名提问
- 选项优先来自 `similarGroup`，避免一眼排除

### 3. 答案验证
- 推荐传入 `--user-reply`，脚本按 daily 中保存的答案确定性判分
- 兼容旧的 `--full-message` LLM 解析方式
- 单词测验答对写入 `wordMastered`，答错写入 `wordWrongList`

### 4. 每日沉淀
- 分析所有历史答题详情
- 生成 `learning-profile.md`（个人学习档案）
- 生成 `next-day-plan.json`（第二天学习方案）
- 自动推送完成通知

### 5. 个性化学习方案
- **第二天方案**：推荐新学哪些行、巩固哪些假名
- `push-strategy.py` 直接读取方案出题
- 精准复习：根据正确率推荐易错假名

---

## 文件结构

```
japanese-learning/
├── SKILL.md              # Skill 文档（触发条件、执行流程）
├── PROJECT.md            # 项目文档（完整流程、配置说明）
├── IMPLEMENTATION.md    # 实现总结（重构记录）
├── README.md            # 本文件
├── .gitignore           # Git 忽略规则
├── scripts/            # 脚本目录
│   ├── push-strategy.py      # 推送脚本（假名模式/单词模式自动切换）
│   ├── gen-word-questions.py # 单词题生成
│   ├── verify-reply.py       # 答案验证
│   ├── infer-progress.py     # 每日沉淀（分析历史、生成档案）
│   ├── gen-questions.py     # 题目生成
│   └── select-kana.py      # 假名选择
└── (数据文件在 workspace/japanese-learning/)
    ├── kana-data.json         # 46 个假名数据
    ├── word-data.json         # 180 个高频词，含 katakana/similarGroup
    ├── progress.json          # 总体进度
    ├── learning-profile.md    # 个人学习档案
    ├── next-day-plan.json    # 第二天方案
    └── daily/                # 每日学习档案
        └── YYYY-MM-DD.json
```

---

## 快速开始

### 1. 安装
将 `japanese-learning` 目录放到 `~/.openclaw/workspace/skills/` 下。

### 2. 配置
编辑 `~/.openclaw/workspace/configs/japanese-learning.json`，配置：
- API Key（DeepSeek API）
- 微信推送参数（channel、target）
- 推送策略（概率、冷却时间）

### 3. 测试推送
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/push-strategy.py
```

### 4. 测试单词学习生成
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/gen-word-questions.py \
  --new 2 --date 2026-07-07 --window morning
```

### 5. 测试单词测验生成
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/gen-word-questions.py \
  --exam --words りす,るす,れい,ろく,わたし,あし --review 1 --wrong 1 --date 2026-07-07
```

### 6. 测试验证
```bash
python3 ~/.openclaw/workspace/skills/japanese-learning/scripts/verify-reply.py \
  --user-reply "1A 2B 3C 4D" \
  --full-message "引用的推送消息..."
```

### 7. 查看档案
```bash
cat ~/.openclaw/workspace/japanese-learning/learning-profile.md
```

---

## 定时任务

| 时间 | 任务 | 说明 |
|------|------|------|
| **每 30 分钟** | 心跳检查 | 落在窗口内推送学习或测验 |
| **每天 01:30** | 每日沉淀 | 分析历史、更新学习档案、生成第二天方案 |

---

## 数据流转

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
push-strategy.py 读取方案和 wordStudyIndex
   ↓
白天推学习，晚间推测验
```

---

## 当前状态（2026-07-07）

- 已掌握：46/46 个基础假名
- 当前默认进入 v3.0 单词先学后考模式
- 单词库：180 个 2-4 假名为主的高频词，覆盖全部基础假名

---

## 🚀 扩展方向（未来）

- [ ] 增加片假名单词（如 アイスクリーム「冰淇淋」）
- [ ] 支持浊音、半浊音、拗音
- [ ] 语音朗读假名（调用 TTS）
- [ ] 生成学习报告图片（可视化进度）
- [ ] 支持多用户（家庭成员：Season、Wandy）

---

## 更新日志

### 2026-07-07 — v3.0 先学后考
- 白天 3 个学习窗口各推 2 个新词，只展示教学
- 22 点后生成晚间 `word-exam` 测验
- 单词库扩充到 180 词，补齐 `katakana` 和 `similarGroup`
- `gen-word-questions.py` 支持 `--exam`、`--words`、相似读音干扰项和片假名提问
- `verify-reply.py`、`infer-progress.py` 兼容 `word-exam` 和学习窗口记录
- progress 新增/维护 `wordStudyIndex`、`wordMasteredByDay`

### 2026-07-06 — 从五十音模式升级为单词模式
- **核心变更**：50音全部学完后，推送策略自动切换到「单词模式」
- 每个窗口：2 个新单词识读题 + 1 个旧词复习 + 1 个错题复习
- 新增 `word-data.json`（58 个 2-4 假名高频纯平假名单词）
- 新增 `scripts/gen-word-questions.py`（单词识读题生成）
- `push-strategy.py` 支持假名完成自动切换单词模式
- `verify-reply.py` 支持 `type: "word"`、`wordMastered` 和 `wordWrongList`
- 清空旧 `wrongKana`，修复 `masteredByRow`（46/46）

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

*最后更新：2026-07-07*
