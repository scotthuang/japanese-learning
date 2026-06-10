# Changelog

## [1.1.3] — 2026-06-11

### 🔧 优化

- **`verify-reply.py`** — 新增 `--user-reply` 参数，与 `--full-message` 分离
  - 新增独立的 `--user-reply` 参数，专用于传入用户答案（如 `1C 2B 3B`）
  - `--full-message` 改为可选，仅作为引用上下文
  - 新增 `parse_user_reply()` 函数，支持空格/连写/大小写格式
  - 新增 `parse_user_reply()` 函数验证层，确保答案提取准确
  - **向后兼容**：只传 `--full-message` 的旧调用方式仍然可用

### 📚 文档

- **`SKILL.md`** — 更新调用示例为推荐的双参数方式
  - 增加 ⚠️ 醒目警告：`--user-reply` 只传用户实际输入，避免混淆正确答案

---

## [1.1.2] — 2026-06-11

### 🐛 修复

- **`push-strategy.py`** — 添加 `fcntl.flock` 文件锁，修复心跳并发触发导致同一窗口推送两套不同题目的竞态条件
  - 新增 `acquire_lock()` 函数 + `/tmp/japanese-push.lock` 锁文件
  - 心跳在 20:35:53 和 20:35:54 连续触发时，只有第一个实例能执行推送
  - 第二个实例自动跳过，日志记录 `⚠️ 发现已有实例在运行`
  - `try/finally` 保证异常退出也释放锁

---

## [1.1.1] — 2026-06-10

### 🐛 修复

- **`push-strategy.py`** — 恢复被重写时遗漏的 `generate_daily_summary()` 函数
- **cron 导入方式** — `from push-strategy import` 改为 `importlib.util` 动态加载，修复文件名含连字符导致的导入失败
- **多窗口适配** — `generate_daily_summary()` 支持新老两种数据格式（windows 对象 / 扁平结构）

---

## [1.1.0] — 2026-06-10

### ✨ 新增：3 时段随机推送

**背景**
用户反馈每天 3 题太少且推送概率只有 30%，希望增加学习密度和随机感。

**变更内容**

- **`push-strategy.py`** — 完全重写推送逻辑
  - 从「每日一次 + 30% 概率」改为「3 时段 + 100% 推送」
  - 三个窗口：早间 08~12 / 午间 13~17 / 晚间 19~22
  - 每个窗口 3 题（1 新学 + 2 复习），题目不重复
  - 各窗口独立：早上没答不影响下午推送
  - 22:00~08:00 静默时段不推送
  - 所有题目答完自动跳过剩余窗口

- **`verify-reply.py`** — 适配多窗口数据模型
  - 支持按窗口匹配用户回复
  - 题目 ID 嵌入窗口名（如 `q_20260610_morning_001`）
  - 兼容新旧格式的文件读取

- **`infer-progress.py`** — 适配多窗口数据模型
  - 聚合所有窗口的答题统计数据

- **`migrate-daily.py`** — **新文件**，旧档案迁移工具
  - 旧格式 `pushed/replied` → 新格式 `windows.morning/afternoon/evening`
  - 支持 `--dry-run` 预览和 `--file` 指定文件
  - 自动备份到 `.migration_backup/`

- **`configs/japanese-learning.json`** — 配置更新
  - 新增 `windows` 配置（3 时段起止时间、标签、emoji）
  - 新增 `questions_per_window` `new_per_window` `review_per_window`
  - 新增 `silent_start` `silent_end`
  - 移除 `random_push_probability`

---

## [1.0.1] — 2026-06-09

### 🐛 修复

- **`verify-reply.py`** — 支持补答历史题目（智能匹配档案文件）
- **总结逻辑** — 从 push 脚本移至 cron 定时任务（01:30），避免重复发送

### 🔧 优化

- 答题可补答任意历史（未回复的）题目，不限当日
- 每日总结写入 `logs/daily_summary.txt`，由 cron 独立管理

---

## [1.0.0] — 2026-06-03

### 🐛 修复

- **`push-strategy.py`** — 修复复习假名永远固定为 3 个特定假名的 bug
- **`push-strategy.py`** — 复习题实时计算，不再依赖 `next-day-plan.json`

### 🔧 优化

- 推送时实时从已掌握列表中按评分选择复习假名
- 推送策略脚本不再读取 `next-day-plan.json`

---

## [0.9.0] — 2026-05-30

### ✨ 新增

- 单词罗马音标注（如 `るす（ru-su）`）
- 选项精简（3 选项而非 5 选项）
- 已学假名复习机制（3 新学 + 2 复习）
- `infer-progress.py` — 进度推理脚本
- `select-kana.py` — 假名选择脚本

### 🔧 优化

- 每日题目从 5 道新学改为 3 新学 + 2 复习
- 推送消息格式更新（含教学 + 提问 + 复习提示）

---

## [0.8.0] — 2026-05-28

### ✨ 新增

- 罗马音在所有问题/助记词中显示
- 五十音图查询功能（`show-kana-table.py`）
- SKILL.md 增加五十音图查询触发规则

---

## [0.7.0] — 2026-05-24

### ✨ 新增

- 学习卡片和助记词添加罗马音标注
- 复习脚本罗马音显示优化
- `review-mastered.py` — 已学假名复习功能（列表/测验/随机三种模式）

---

## [0.6.0] — 2026-05-23

### ✨ 新增

- **日语五十音学习系统初始版本**
- 每日 5 道假名选择题，随机 30% 概率推送
- 混元 API 接入（LLM 推理解析答案）
- `verify-reply.py` — LLM 推理答案验证（大改造版）
- `push-strategy.py` — 推送策略脚本
- `gen-questions.py` — 题目生成脚本
- `verify-config.py` — 配置验证脚本
- 学习进度追踪（mastered 列表、daily 档案）
- 微信推送集成（`openclaw-weixin` 渠道）
- 完整日志系统（main.log / push.log / infer-error.log）
