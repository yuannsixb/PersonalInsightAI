# window.py — 当前窗口获取 + URL 提取
# 从 agent.py 拆分，让 agent.py 专注于采集调度

import re


def get_active_window():
    """获取当前活跃窗口，返回 (进程名, 窗口标题)"""
    try:
        import ctypes
        import psutil
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd == 0:
            return None, None

        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc = psutil.Process(pid.value)
        return proc.name(), title
    except Exception:
        return None, None


def is_browser(process_name):
    """判断是否为浏览器进程"""
    name = (process_name or '').lower().strip()
    browsers = ['chrome.exe', 'msedge.exe', 'firefox.exe',
                'opera.exe', 'brave.exe', 'safari.exe']
    return name in browsers


def extract_url(title):
    """从窗口标题中提取域名（轻量版）"""
    if not title:
        return ''
    title_lower = title.lower()
    domain_keywords = {
        'chatgpt': 'chat.openai.com', 'openai': 'openai.com',
        'claude': 'claude.ai', 'deepseek': 'deepseek.com',
        'github': 'github.com', 'douyin': 'douyin.com',
        'bilibili': 'www.bilibili.com', 'youtube': 'www.youtube.com',
        'leetcode': 'leetcode.cn', 'nowcoder': 'www.nowcoder.com',
        'csdn': 'csdn.net', 'zhihu': 'www.zhihu.com',
        'taobao': 'www.taobao.com', 'jd': 'www.jd.com',
        'baidu': 'www.baidu.com', 'google': 'www.google.com',
        'stackoverflow': 'stackoverflow.com', 'kimi': 'kimi.moonshot.cn',
        'notion': 'notion.so', 'feishu': 'www.feishu.cn',
        '抖音': 'douyin.com', '哔哩': 'www.bilibili.com',
        '知乎': 'www.zhihu.com', '淘宝': 'www.taobao.com',
    }
    for keyword, url in domain_keywords.items():
        if keyword in title_lower:
            return url
    # 从标题末尾提取域名
    match = re.search(r'(?:^|[\s\-–—])((?:www\.)?[a-z0-9][a-z0-9\-]*\.[a-z]{2,})', title)
    if match:
        return match.group(1)
    return ''
