# config.py — 全局配置
# 采集/分析相关参数统一放这里，方便修改

import os

# 项目根目录
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# 采集间隔（秒）
COLLECT_INTERVAL = 10

# 分析间隔（分钟）
ANALYSIS_INTERVAL = 360  # 6 小时

# 状态文件
STATUS_FILE = os.path.join(ROOT_DIR, 'data', 'agent_status.json')
PAUSE_FILE = os.path.join(ROOT_DIR, 'data', '.paused')

# 浏览器进程列表
BROWSER_PROCESSES = [
    'chrome.exe', 'msedge.exe', 'firefox.exe',
    'opera.exe', 'brave.exe', 'safari.exe',
]
