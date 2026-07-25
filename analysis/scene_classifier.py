# scene_classifier.py — 场景分类器 v2.3.0
#
# v2.3.0 改动：
#   1. 增加分类结果缓存（同一窗口短时间不重复判断）
#   2. 支持传入内存用户规则缓存，避免每分类一次查一次数据库
#   3. 简化分类优先级：个人知识库 > 网站知识库 > 应用知识库 > 窗口标题 > unknown

import os
import csv

# ============================================================
# 关键词知识库（一次性加载）
# ============================================================
_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'scene_dictionary.csv'
)

KEYWORDS_SORTED = []
try:
    with open(_CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            kw = row['keyword'].strip().lower()
            scene = row['scene'].strip()
            if kw and scene:
                KEYWORDS_SORTED.append((kw, scene))
    KEYWORDS_SORTED.sort(key=lambda x: -len(x[0]))
    print(f'[词库] 加载 {len(KEYWORDS_SORTED)} 条关键词')
except Exception as e:
    print(f'警告: scene_dictionary.csv 加载失败: {e}')
    KEYWORDS_SORTED = [
        ('chatgpt', 'study'), ('leetcode', 'study'),
        ('github', 'work'), ('excel', 'work'),
        ('抖音', 'leisure'), ('bilibili', 'leisure'), ('淘宝', 'life'),
    ]

# ============================================================
# 进程名兜底
# ============================================================
PROCESS_MAP = {
    'pycharm64.exe': 'work', 'code.exe': 'work', 'idea64.exe': 'work',
    'sublime_text.exe': 'work', 'notepad++.exe': 'work',
    'WindowsTerminal.exe': 'work', 'cmd.exe': 'work', 'powershell.exe': 'work',
    'WINWORD.EXE': 'work', 'EXCEL.EXE': 'work', 'POWERPNT.EXE': 'work',
    'OUTLOOK.EXE': 'work',
    'DingTalk.exe': 'work', 'Feishu.exe': 'work', 'Lark.exe': 'work',
    'TencentMeeting.exe': 'work', 'zoom.exe': 'work',
    'WeChat.exe': 'leisure', 'Weixin.exe': 'leisure', 'QQ.exe': 'leisure',
    'potplayer.exe': 'leisure', 'Spotify.exe': 'leisure', 'CloudMusic.exe': 'leisure',
    'BF2042.exe': 'leisure', 'LeagueClient.exe': 'leisure',
    'Steam.exe': 'leisure', 'GenshinImpact.exe': 'leisure',
    'chrome.exe': 'browser', 'msedge.exe': 'browser', 'firefox.exe': 'browser',
    'explorer.exe': 'life',
}

# ============================================================
# 分类结果缓存
# ============================================================
_classification_cache = {}
_MAX_CACHE_SIZE = 500


def clear_cache():
    _classification_cache.clear()


def classify(process_name, window_title='', user_rules_cache=None):
    """
    分类一条行为记录。

    分类优先级:
      1. 用户个人知识库（最高）
         - 规则带关键词：进程名 + 标题关键词同时匹配
         - 规则不带关键词：纯进程名匹配
      2. 网站/窗口标题关键词匹配
      3. 应用进程名查表
      4. 兜底 unknown

    参数 user_rules_cache:
      - 旧格式: {app_name: scene} 字典
      - 新格式: (simple_dict, keyword_list) 元组
    """
    name = (process_name or '').lower().strip()
    title = (window_title or '').lower().strip()
    cache_key = f'{name}|{title}'

    from database.db import _expand_search_names

    # 缓存命中
    if cache_key in _classification_cache:
        return _classification_cache[cache_key]

    # 1. 用户个人知识库
    if user_rules_cache is not None:
        # 判断是新格式还是旧格式
        if isinstance(user_rules_cache, tuple) and len(user_rules_cache) == 2:
            simple, keyword = user_rules_cache
            search_names = _expand_search_names(name)
            # 1a. 先查带关键词的规则
            if title:
                for app, kw, scene in keyword:
                    for sname in search_names:
                        if sname == app and kw in title:
                            _classification_cache[cache_key] = scene
                            return scene
            # 1b. 再查纯进程名规则
            for sname in search_names:
                if sname in simple:
                    _classification_cache[cache_key] = simple[sname]
                    return simple[sname]
        else:
            # 旧格式兼容: {app_name: scene}
            if name in user_rules_cache:
                _classification_cache[cache_key] = user_rules_cache[name]
                return user_rules_cache[name]
            base = name[:-4] if name.endswith('.exe') else name
            with_exe = name + '.exe' if not name.endswith('.exe') else name
            if base in user_rules_cache:
                _classification_cache[cache_key] = user_rules_cache[base]
                return user_rules_cache[base]
            if with_exe in user_rules_cache:
                _classification_cache[cache_key] = user_rules_cache[with_exe]
                return user_rules_cache[with_exe]
    else:
        # 没有缓存时查数据库
        try:
            from database.db import match_user_rule
            user_scene = match_user_rule(name, title)
            if user_scene:
                _classification_cache[cache_key] = user_scene
                return user_scene
        except ImportError:
            pass

    # 2. 窗口标题关键词匹配（长词优先）
    if title:
        for kw, scene in KEYWORDS_SORTED:
            if kw in title:
                _classification_cache[cache_key] = scene
                return scene

    # 3. 进程名查表
    if name in PROCESS_MAP:
        scene = PROCESS_MAP[name]
        if scene == 'browser':
            scene = _classify_browser(title)
        _classification_cache[cache_key] = scene
        return scene

    # 4. 兜底 unknown
    _classification_cache[cache_key] = 'unknown'
    return 'unknown'


def _classify_browser(title):
    """浏览器的窗口标题分类"""
    if not title:
        return 'browser'
    tl = title.lower()
    for kw, scene in KEYWORDS_SORTED:
        if kw in tl:
            return scene
    return 'browser'


def batch_classify(df, user_rules_cache=None):
    """批量分类。可传入 user_rules_cache 减少数据库查询"""
    import pandas as pd
    df = df.copy()
    scenes = []
    for _, row in df.iterrows():
        name = row.get('process_name', '')
        title = row.get('window_title', '')
        if pd.isna(name): name = ''
        if pd.isna(title): title = ''
        scenes.append(classify(str(name), str(title), user_rules_cache))
    df['scene'] = scenes
    return df


# ============================================================
# 测试
# ============================================================
if __name__ == '__main__':
    test_cases = [
        ('msedge.exe', 'ChatGPT - OpenAI'),
        ('msedge.exe', 'GitHub - Pull Request'),
        ('Weixin.exe', '微信'),
        ('Code.exe', 'agent.py - PersonalInsightAI'),
    ]
    print('场景分类 v2.3.0 测试')
    print('=' * 60)
    for exe, title in test_cases:
        s = classify(exe, title)
        print(f'  [{s:8s}] {exe:20s} | {title}')
