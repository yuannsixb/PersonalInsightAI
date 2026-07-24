# database/db.py — SQLite 数据库操作
# v2.3.0 — 索引优化 + 批量写入 + 历史清理 + 连接复用

import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'insight.db')

# 批量写入缓存
_batch_buffer = []
_BATCH_SIZE = 10

# 单例连接（程序运行期间复用，避免反复 open/close）
_connection = None


def get_conn():
    global _connection
    try:
        # 检查已有连接是否健康
        if _connection is not None:
            _connection.execute('SELECT 1')
            return _connection
    except Exception:
        # 连接已死，重建
        _connection = None
    # 新建连接
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    _connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    _connection.row_factory = sqlite3.Row
    _connection.execute('PRAGMA journal_mode=WAL')
    return _connection


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # 行为日志表
    c.execute('''
        CREATE TABLE IF NOT EXISTS behavior_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date   TEXT NOT NULL,
            start_time   TEXT NOT NULL,
            duration_min REAL DEFAULT 0.5,
            process_name TEXT NOT NULL,
            scene        TEXT DEFAULT 'unknown',
            window_title TEXT,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 高频查询索引
    c.execute('CREATE INDEX IF NOT EXISTS idx_log_date ON behavior_log(event_date)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_log_scene ON behavior_log(scene)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_log_process ON behavior_log(process_name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_log_created ON behavior_log(created_at)')

    # 每日汇总表
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_summary (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_date TEXT NOT NULL,
            scene        TEXT NOT NULL,
            total_min    REAL DEFAULT 0,
            record_count INTEGER DEFAULT 0,
            UNIQUE(summary_date, scene)
        )
    ''')

    # 洞察报告表
    c.execute('''
        CREATE TABLE IF NOT EXISTS insight_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            report_type TEXT NOT NULL,
            report_text TEXT NOT NULL
        )
    ''')

    # 配置表
    c.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # 用户知识库
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_scene_dictionary (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name            TEXT NOT NULL,
            window_title_keyword TEXT DEFAULT '',
            domain              TEXT DEFAULT '',
            scene               TEXT NOT NULL,
            create_time         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(app_name, window_title_keyword)
        )
    ''')

    defaults = [
        ('采集间隔', '30'), ('分析间隔', '360'),
        ('最后分析时间', ''), ('版本', '2.3.0'),
    ]
    c.executemany('INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)', defaults)
    conn.commit()


# ============================================================
# 批量写入
# ============================================================

def buffer_behavior(event_date, start_time, duration_min, process_name, scene, window_title=''):
    """将行为数据存入缓冲区，积累到 BATCH_SIZE 条再批量写入"""
    global _batch_buffer
    _batch_buffer.append((event_date, start_time, duration_min, process_name, scene, window_title))
    if len(_batch_buffer) >= _BATCH_SIZE:
        flush_behavior_buffer()


def flush_behavior_buffer():
    """将缓冲区中的数据一次性写入数据库"""
    global _batch_buffer
    if not _batch_buffer:
        return
    conn = get_conn()
    conn.executemany(
        'INSERT INTO behavior_log (event_date, start_time, duration_min, process_name, scene, window_title) '
        'VALUES (?, ?, ?, ?, ?, ?)',
        _batch_buffer
    )
    conn.commit()
    _batch_buffer = []
    

# ============================================================
# 常规查询
# ============================================================

def get_behavior_count():
    conn = get_conn()
    cnt = conn.execute('SELECT COUNT(*) FROM behavior_log').fetchone()[0]
    return cnt


def get_scene_count():
    conn = get_conn()
    rows = conn.execute(
        'SELECT scene, COUNT(*) as cnt, SUM(duration_min) as total '
        'FROM behavior_log GROUP BY scene'
    ).fetchall()
    return [dict(r) for r in rows]


def update_daily_summary(event_date, scene, duration_min):
    conn = get_conn()
    conn.execute('''
        INSERT INTO daily_summary (summary_date, scene, total_min, record_count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(summary_date, scene) DO UPDATE SET
            total_min = total_min + ?,
            record_count = record_count + 1
    ''', (event_date, scene, duration_min, duration_min))
    conn.commit()


def get_weekly_summary():
    conn = get_conn()
    rows = conn.execute('''
        SELECT summary_date, scene, total_min FROM daily_summary
        WHERE summary_date >= date('now', '-7 days')
        ORDER BY summary_date
    ''').fetchall()
    return [dict(r) for r in rows]


def save_report(report_type, report_text):
    conn = get_conn()
    conn.execute(
        'INSERT INTO insight_reports (report_type, report_text) VALUES (?, ?)',
        (report_type, report_text)
    )
    conn.commit()


def get_latest_report(report_type='auto'):
    conn = get_conn()
    row = conn.execute(
        'SELECT * FROM insight_reports WHERE report_type = ? ORDER BY id DESC LIMIT 1',
        (report_type,)
    ).fetchone()
    return dict(row) if row else None


def get_config(key):
    conn = get_conn()
    row = conn.execute('SELECT value FROM config WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else None


def set_config(key, value):
    conn = get_conn()
    conn.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, value))
    conn.commit()


# ============================================================
# 历史数据清理（默认保留 90 天）
# ============================================================

def cleanup_old_data(retain_days=90):
    """删除 retain_days 天之前的详细行为日志"""
    cutoff = (datetime.now() - timedelta(days=retain_days)).strftime('%Y-%m-%d')
    conn = get_conn()
    deleted = conn.execute('DELETE FROM behavior_log WHERE event_date < ?', (cutoff,)).rowcount
    if deleted:
        conn.execute('DELETE FROM daily_summary WHERE summary_date < ?', (cutoff,))
        conn.commit()
        print(f'[清理] 已删除 {deleted} 条 {cutoff} 前的历史记录')


# ============================================================
# 用户知识库
# ============================================================

_PROCESS_ALIASES = {
    '微信': 'weixin.exe', '企业微信': 'wxwork.exe',
    '钉钉': 'dingtalk.exe', '飞书': 'feishu.exe',
    '腾讯会议': 'tencentmeeting.exe', 'zoom': 'zoom.exe',
    'steam': 'steam.exe', '网易云音乐': 'cloudmusic.exe',
    '百度网盘': 'baidunetdisk.exe', '阿里云盘': 'aliyundrive.exe',
    '有道词典': 'youdaodict.exe', '百度输入法': 'baiduinput.exe',
    '搜狗输入法': 'sogouinput.exe', '向日葵': 'sunloginclient.exe',
    'TeamViewer': 'teamviewer.exe', '腾讯视频': 'qqlive.exe',
    '爱奇艺': 'qiyi.exe', '优酷': 'youku.exe',
    '微信读书': 'weread.exe', 'chrome': 'chrome.exe',
    'edge': 'msedge.exe', 'firefox': 'firefox.exe',
    '微信聊天': 'weixin.exe', 'WeChat': 'weixin.exe', 'WX': 'weixin.exe',
}


def _expand_search_names(name):
    """展开进程名为可能的搜索形式"""
    n = name.lower().strip()
    forms = {n}
    if n.endswith('.exe'):
        forms.add(n[:-4])
    else:
        forms.add(n + '.exe')
    for alias, proc in _PROCESS_ALIASES.items():
        al = alias.lower(); pl = proc.lower()
        if n == al or n == pl or n == pl.replace('.exe', ''):
            forms.add(al); forms.add(pl)
    return forms


def add_user_rule(app_name, scene, window_title_keyword='', domain=''):
    conn = get_conn()
    conn.execute('''
        INSERT INTO user_scene_dictionary (app_name, window_title_keyword, domain, scene)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(app_name, window_title_keyword) DO UPDATE SET
            scene = excluded.scene, domain = excluded.domain, create_time = CURRENT_TIMESTAMP
    ''', (app_name, window_title_keyword, domain, scene))
    conn.commit()


def get_user_rules():
    conn = get_conn()
    rows = conn.execute(
        'SELECT id, app_name, window_title_keyword, domain, scene, create_time '
        'FROM user_scene_dictionary ORDER BY create_time DESC'
    ).fetchall()
    return [dict(r) for r in rows]


def load_user_rules_cache():
    """一次性加载所有用户规则到内存（返回 dict: process_name -> scene）"""
    conn = get_conn()
    rows = conn.execute(
        'SELECT app_name, scene FROM user_scene_dictionary WHERE window_title_keyword = ?',
        ('',)
    ).fetchall()
    # 连接复用，不关闭
    return {r['app_name']: r['scene'] for r in rows}


def match_user_rule(process_name, window_title='', rules_cache=None):
    """
    匹配用户知识库。
    支持传入内存缓存 rules_cache 避免每次查数据库。
    """
    name = (process_name or '').lower().strip()
    title = (window_title or '').lower().strip()
    search_names = _expand_search_names(name)

    if rules_cache is not None:
        # 走内存缓存
        for sname in search_names:
            if sname in rules_cache:
                return rules_cache[sname]
        return None

    # 走数据库查询
    conn = get_conn()
    for sname in search_names:
        rows = conn.execute(
            'SELECT scene FROM user_scene_dictionary WHERE app_name = ? AND window_title_keyword = ?',
            (sname, '')
        ).fetchall()
        if rows:
            return rows[0]['scene']
    return None


def update_user_rule(rule_id, new_scene):
    conn = get_conn()
    conn.execute(
        'UPDATE user_scene_dictionary SET scene = ?, create_time = CURRENT_TIMESTAMP WHERE id = ?',
        (new_scene, rule_id)
    )
    conn.commit()


def delete_user_rule(rule_id):
    conn = get_conn()
    conn.execute('DELETE FROM user_scene_dictionary WHERE id = ?', (rule_id,))
    conn.commit()


def get_user_rules_count():
    conn = get_conn()
    return conn.execute('SELECT COUNT(*) FROM user_scene_dictionary').fetchone()[0]
