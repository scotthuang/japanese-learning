#!/usr/bin/env python3
"""
日语学习系统配置验证脚本
验证配置文件、脚本路径、日志路径是否正确
"""

import json
import os
import sys

def check_file(path, description, must_exist=True):
    """检查文件是否存在"""
    expanded = os.path.expanduser(path)
    if os.path.exists(expanded):
        print(f"✅ {description}: {expanded}")
        return True
    else:
        if must_exist:
            print(f"❌ {description} 不存在: {expanded}")
            return False
        else:
            print(f"⚠️  {description} 不存在（可选）: {expanded}")
            return True

def main():
    print("=" * 60)
    print("日语学习系统配置验证")
    print("=" * 60)
    print()
    
    # 1. 检查配置文件
    print("【1. 配置文件】")
    config_file = "~/.openclaw/workspace/configs/japanese-learning.json"
    if not check_file(config_file, "配置文件"):
        return False
    
    # 读取配置
    try:
        with open(os.path.expanduser(config_file), "r", encoding="utf-8") as f:
            config = json.load(f)
        print(f"✅ 配置文件格式正确")
    except Exception as e:
        print(f"❌ 配置文件解析失败: {e}")
        return False
    
    print()
    
    # 2. 检查数据目录
    print("【2. 数据目录】")
    data_dir = config["workspace"]["root"]
    check_file(data_dir, "数据根目录")
    check_file(config["workspace"]["daily_dir"], "每日档案目录")
    check_file(config["workspace"]["kana_data"], "假名数据文件")
    check_file(config["workspace"]["progress_file"], "进度文件")
    
    print()
    
    # 3. 检查日志目录（新结构）
    print("【3. 日志目录】")
    log_dir = config["logs"]["dir"]
    check_file(log_dir, "日志根目录", must_exist=False)
    
    # 确保日志目录存在
    expanded_log_dir = os.path.expanduser(log_dir)
    if not os.path.exists(expanded_log_dir):
        print(f"   正在创建日志目录: {expanded_log_dir}")
        os.makedirs(expanded_log_dir, exist_ok=True)
    
    check_file(config["logs"]["main_log"], "主日志文件", must_exist=False)
    check_file(config["logs"]["infer_error_log"], "推理错误日志", must_exist=False)
    check_file(config["logs"]["push_log"], "推送日志", must_exist=False)
    check_file(config["logs"]["script_log"], "脚本日志", must_exist=False)
    
    print()
    
    # 4. 检查脚本文件
    print("【4. 脚本文件】")
    scripts_dir = "~/.openclaw/workspace/skills/japanese-learning/scripts"
    check_file(scripts_dir, "脚本目录")
    
    scripts = [
        "push-strategy.py",
        "infer-progress.py",
        "verify-reply.py",
        "gen-questions.py",
        "select-kana.py",
        "verify-config.py"
    ]
    
    for script in scripts:
        script_path = os.path.join(os.path.expanduser(scripts_dir), script)
        if os.path.exists(script_path):
            print(f"✅ 脚本: {script}")
        else:
            print(f"❌ 脚本缺失: {script}")
    
    print()
    
    # 5. 检查配置项
    print("【5. 配置项检查】")
    print(f"  API Provider: {config.get('api', {}).get('provider', '未配置')}")
    print(f"  API Model: {config.get('api', {}).get('model', '未配置')}")
    
    # 检查 API key 是否配置
    api_key = config.get('api', {}).get('api_key', '')
    if api_key and api_key != '<API_KEY>':
        print(f"  ✅ API Key: 已配置（长度 {len(api_key)} 字符）")
    else:
        print(f"  ❌ API Key: 未配置或使用了占位符")
    
    print(f"  Base URL: {config.get('api', {}).get('base_url', '未配置')}")
    print(f"  推送间隔: {config.get('push_strategy', {}).get('interval_seconds', 0)}秒")
    print(f"  推送概率: {config.get('push_strategy', {}).get('random_push_probability', 0)}%")
    print(f"  每日题数: {config.get('push_strategy', {}).get('questions_per_day', 0)}")
    print(f"  微信渠道: {config.get('wechat', {}).get('channel', '未配置')}")
    
    print()
    print("=" * 60)
    print("✅ 验证完成！")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
