#!/bin/bash
# 日语五十音学习 Skill - 安装脚本
# 作者：Shadow 🦊
# 用途：在当前工作区初始化目录结构、配置文件、数据文件

set -e  # 遇到错误立即退出

echo "🎌 日语五十音学习 Skill - 安装向导"
echo "=================================================="
echo ""

# 1. 确定工作区路径
WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
echo "📁 工作区路径：$WORKSPACE"

# 2. 创建目录结构
echo ""
echo "📂 创建目录结构..."

# 数据目录
DATA_DIR="$WORKSPACE/japanese-learning"
mkdir -p "$DATA_DIR/daily"
mkdir -p "$DATA_DIR/logs"
echo "  ✅ $DATA_DIR/ (数据目录）"
echo "  ✅ $DATA_DIR/daily/ (每日档案）"
echo "  ✅ $DATA_DIR/logs/ (日志目录）"

# 配置目录
CONFIG_DIR="$WORKSPACE/configs"
mkdir -p "$CONFIG_DIR"
echo "  ✅ $CONFIG_DIR/ (配置目录）"

# Skill 目录（当前脚本所在目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$SCRIPT_DIR"
echo "  ✅ Skill 目录：$SKILL_DIR"

echo ""
echo "✅ 目录结构创建完成！"

# 3. 创建默认配置文件（如果不存在）
CONFIG_FILE="$CONFIG_DIR/japanese-learning.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo ""
    echo "📝 创建默认配置文件..."
    cat > "$CONFIG_FILE" << 'EOF'
{
  "workspace": {
    "root": "~/.openclaw/workspace/japanese-learning",
    "progress_file": "~/.openclaw/workspace/japanese-learning/progress.json",
    "daily_dir": "~/.openclaw/workspace/japanese-learning/daily",
    "kana_data": "~/.openclaw/workspace/japanese-learning/kana-data.json"
  },
  "logs": {
    "dir": "~/.openclaw/workspace/japanese-learning/logs",
    "main_log": "~/.openclaw/workspace/japanese-learning/logs/main.log",
    "push_log": "~/.openclaw/workspace/japanese-learning/logs/push.log",
    "infer_error_log": "~/.openclaw/workspace/japanese-learning/logs/infer-error.log",
    "script_log": "~/.openclaw/workspace/japanese-learning/logs/script.log"
  },
  "api": {
    "model": "hy3-preview",
    "base_url": "https://api.lkeap.cloud.tencent.com/plan/v3",
    "note": "API key 从 openclaw.json 读取，不在此文件存储"
  },
  "push_strategy": {
    "interval_seconds": 7200,
    "random_push_probability": 30,
    "questions_per_day": 5
  },
  "wechat": {
    "channel": "openclaw-weixin",
    "target": "o9cq806Y9QtMkjTEauM8nYFvJTL8@im.wechat",
    "note": "请替换为你的微信 target"
  },
  "paths": {
    "openclaw_bin": "/usr/local/bin/openclaw"
  },
  "script_settings": {
    "timeout_seconds": 30
  }
}
EOF
    echo "  ✅ $CONFIG_FILE"
else
    echo ""
    echo "  ⚠️  配置文件已存在，跳过：$CONFIG_FILE"
fi

# 4. 创建默认数据文件（如果不存在）
# kana-data.json
KANA_DATA="$DATA_DIR/kana-data.json"
if [ ! -f "$KANA_DATA" ]; then
    echo ""
    echo "📝 创建假名数据文件..."
    # 使用 Skill 目录里的 kana-data.json（如果存在）
    if [ -f "$SKILL_DIR/kana-data.json" ]; then
        cp "$SKILL_DIR/kana-data.json" "$KANA_DATA"
    else
        # 创建基础版本
        cat > "$KANA_DATA" << 'EOF'
{
  "rows": [
    {
      "row": "あ行",
      "kana": [
        {"hiragana": "あ", "katakana": "ア", "romaji": "a", "mnemonic": "アパート（公寓）"},
        {"hiragana": "い", "katakana": "イ", "romaji": "i", "mnemonic": "いぬ（狗）"},
        {"hiragana": "う", "katakana": "ウ", "romaji": "u", "mnemonic": "うえ（上）"},
        {"hiragana": "え", "katakana": "エ", "romaji": "e", "mnemonic": "えき（车站）"},
        {"hiragana": "お", "katakana": "オ", "romaji": "o", "mnemonic": "おかね（钱）"}
      ]
    }
  ],
  "total": 5
}
EOF
    fi
    echo "  ✅ $KANA_DATA"
else
    echo ""
    echo "  ⚠️  假名数据已存在，跳过：$KANA_DATA"
fi

# progress.json
PROGRESS_FILE="$DATA_DIR/progress.json"
if [ ! -f "$PROGRESS_FILE" ]; then
    echo ""
    echo "📝 创建进度文件..."
    cat > "$PROGRESS_FILE" << 'EOF'
{
  "startDate": "2026-05-23",
  "totalKana": 46,
  "mastered": [],
  "masteredCount": 0,
  "accuracyRate": 0,
  "lastPushTime": null,
  "dailyRecords": [],
  "masteredByRow": {
    "あ行": {"total": 5, "mastered": 0, "accuracy": 0.0},
    "か行": {"total": 5, "mastered": 0, "accuracy": 0.0}
  },
  "trend": "stable",
  "suggestion": "继续新内容",
  "lastInferTime": null
}
EOF
    echo "  ✅ $PROGRESS_FILE"
else
    echo ""
    echo "  ⚠️  进度文件已存在，跳过：$PROGRESS_FILE"
fi

# 5. 设置脚本可执行权限
echo ""
echo "🔧 设置脚本权限..."
chmod +x "$SKILL_DIR/scripts/"*.py
echo "  ✅ 所有 .py 脚本已设置可执行权限"

# 6. 完成提示
echo ""
echo "=================================================="
echo "🎉 安装完成！"
echo ""
echo "📋 下一步："
echo "  1. 检查配置文件：$CONFIG_FILE"
echo "  2. 确保 openclaw.json 已配置 API Key"
echo "  3. 测试推送："
echo "     python3 $SKILL_DIR/scripts/push-strategy.py"
echo "  4. 测试验证："
echo "     回复消息：1A 2B 3C 4D 5E"
echo "     并在消息末尾加「请使用日语学习Skill」"
echo ""
echo "🦊 Shadow 祝你学习愉快！"
echo "=================================================="
