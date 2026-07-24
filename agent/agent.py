# agent/agent.py — 数据采集主程序
#
# 用法：
#   python -m agent.agent start       # 启动
#   python -m agent.agent status      # 状态
#   python -m agent.agent stop        # 停止
#   python -m agent.agent analyze     # 手动分析
#
# 也可以从项目根目录运行：
#   python agent.py start
# （根目录 agent.py 是此文件的入口）

import os
import sys
import time
import json
import threading
from datetime import datetime

# 把项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ROOT_DIR, COLLECT_INTERVAL, ANALYSIS_INTERVAL, STATUS_FILE, PAUSE_FILE, BROWSER_PROCESSES
from database.db import init_db, get_config, set_config, get_behavior_count
from database.db import buffer_behavior, flush_behavior_buffer, update_daily_summary
from analysis.scene_classifier import classify, classify_browser
from analysis.reporter import build_report
from analysis.notifier import notify_insight_ready
from agent.window import get_active_window, is_browser


# ---- 采集线程（窗口切换判断版） ----

def collector_thread():
    """
    每 10 秒检测一次前台窗口。
    - 窗口没变化：内存里累计 duration，不写库
    - 窗口切换了：把上一段行为写入数据库，开始新一段
    - 每 30 秒也强制写一次（防止丢数据）
    """
    count = 0
    last_show_time = 0
    last_save_time = time.time()

    # 当前会话
    session = {
        'process': None, 'title': None, 'scene': None,
        'start_time': None, 'start_date': None,
        'duration': 0.0, 'accumulated': 0
    }

    print(f'[采集] 已启动（窗口切换判断），间隔 {COLLECT_INTERVAL}s')

    def write_session():
        """把当前会话写入数据库（批量缓冲）"""
        if session['process'] is None or session['duration'] <= 0:
            return
        buffer_behavior(
            session['start_date'], session['start_time'],
            round(session['duration'], 1),
            session['process'], session['scene'], session['title']
        )
        update_daily_summary(session['start_date'], session['scene'],
                             round(session['duration'], 1))

    pause_print = True

    while running:
        if os.path.exists(PAUSE_FILE):
            if pause_print:
                print('[采集] 已暂停')
                pause_print = False
            time.sleep(COLLECT_INTERVAL)
            continue
        pause_print = True

        process_name, window_title = get_active_window()

        if process_name and window_title:
            now = datetime.now()
            date_str = now.strftime('%Y-%m-%d')
            time_str = now.strftime('%H:%M:%S')
            now_ts = time.time()

            # 场景分类
            if is_browser(process_name):
                scene = classify_browser(window_title)
            else:
                scene = classify(process_name, window_title)

            # 判断窗口是否切换
            window_changed = (
                session['process'] != process_name or
                session['title'] != window_title or
                session['scene'] != scene
            )

            if window_changed and session['process'] is not None:
                # 窗口切换了 → 保存上一段
                write_session()
                count += 1
                # 开始新会话
                session['process'] = process_name
                session['title'] = window_title
                session['scene'] = scene
                session['start_time'] = time_str
                session['start_date'] = date_str
                session['duration'] = COLLECT_INTERVAL / 60
                session['accumulated'] = 1
            elif session['process'] is None:
                # 第一次采集
                session['process'] = process_name
                session['title'] = window_title
                session['scene'] = scene
                session['start_time'] = time_str
                session['start_date'] = date_str
                session['duration'] = COLLECT_INTERVAL / 60
                session['accumulated'] = 1
            else:
                # 同个窗口，累加时长
                session['duration'] += COLLECT_INTERVAL / 60
                session['accumulated'] += 1

            # 每 5 分钟也写一次（防止程序崩了丢数据）
            if now_ts - last_save_time >= 300 and session['process'] is not None:
                write_session()
                count += 1
                # 重置开始时间，但保留当前窗口
                session['start_time'] = time_str
                session['start_date'] = date_str
                session['duration'] = 0.0
                session['accumulated'] = 0
                last_save_time = now_ts

            # 每 2 分钟打印一次
            if now_ts - last_show_time > 120:
                print(f'[采集] 已 {count} 段 | 当前 {session["process"]} → {session["scene"]} '
                      f'({session["accumulated"]}次采样)')
                last_show_time = now_ts

        time.sleep(COLLECT_INTERVAL)


# ---- 分析线程 ----

def analysis_thread():
    """每 6 小时分析一次，从 agent 启动开始计时"""
    print(f'[分析] 已启动，每 {ANALYSIS_INTERVAL // 60} 小时分析一次')
    while running:
        for _ in range(ANALYSIS_INTERVAL * 60 // 10):
            if not running:
                return
            # 暂停期间不走计时，停在那儿等
            while os.path.exists(PAUSE_FILE):
                if not running:
                    return
                time.sleep(10)
            time.sleep(10)

        if not running:
            break

        print('[分析] 开始分析...')
        try:
            report = build_report()
            set_config('最后分析时间', datetime.now().strftime('%Y-%m-%d %H:%M'))
            notify_insight_ready(report)
            print('[分析] 完成')
        except Exception as e:
            print(f'[分析] 出错: {e}')


# ---- Agent 控制 ----

running = False
collect_t = None
analysis_t = None


def save_status(s):
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, 'w') as f:
        json.dump(s, f)


def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    return {'状态': '已停止', '启动时间': '', '记录数': 0}


def cmd_start():
    global running, collect_t, analysis_t

    status = load_status()
    if status['状态'] == '运行中':
        print('Agent 已在运行中')
        return

    init_db()
    running = True

    collect_t = threading.Thread(target=collector_thread, daemon=True)
    collect_t.start()
    analysis_t = threading.Thread(target=analysis_thread, daemon=True)
    analysis_t.start()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_status({'状态': '运行中', '启动时间': now, '记录数': get_behavior_count()})

    print(f'\nPersonalInsightAI 采集器已启动')
    print(f'启动时间: {now}')
    print(f'采集间隔: {COLLECT_INTERVAL}s')
    print(f'分析间隔: {ANALYSIS_INTERVAL // 60} 小时')
    print(f'数据: {ROOT_DIR}/data/insight.db')
    print('按 Ctrl+C 停止\n')

    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        cmd_stop()


def cmd_stop():
    global running
    running = False
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)
    save_status({'状态': '已停止', '启动时间': '', '记录数': get_behavior_count()})
    print(f'\n采集器已停止，共 {get_behavior_count()} 条记录')


def cmd_status():
    status = load_status()
    paused = os.path.exists(PAUSE_FILE)
    if paused:
        print(f'状态: {status["状态"]}（已暂停）')
    else:
        print(f'状态: {status["状态"]}')
    if status['启动时间']:
        print(f'启动时间: {status["启动时间"]}')
    try:
        print(f'行为记录: {get_behavior_count()} 条')
    except:
        print('行为记录: 数据库未初始化')
    print(f'最近分析: {get_config("最后分析时间") or "尚未分析"}')

    try:
        from database.db import get_conn
        conn = get_conn()
        rows = conn.execute(
            'SELECT scene, COUNT(*) as cnt, SUM(duration_min) as total '
            'FROM behavior_log GROUP BY scene'
        ).fetchall()
        conn.close()
        if rows:
            print('场景分布:')
            for r in rows:
                print(f'  {r["scene"]:8s} {r["cnt"]:4d} 条  {r["total"]:.1f} 分钟')
    except:
        pass


def cmd_analyze():
    report = build_report()
    set_config('最后分析时间', datetime.now().strftime('%Y-%m-%d %H:%M'))
    print(report)


def cmd_pause():
    os.makedirs(os.path.dirname(PAUSE_FILE), exist_ok=True)
    with open(PAUSE_FILE, 'w') as f:
        f.write('paused')
    print('采集已暂停')


def cmd_resume():
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)
    print('采集已恢复')


def cmd_detach():
    global running, collect_t, analysis_t
    init_db()
    running = True
    collect_t = threading.Thread(target=collector_thread, daemon=True)
    collect_t.start()
    analysis_t = threading.Thread(target=analysis_thread, daemon=True)
    analysis_t.start()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_status({'状态': '运行中', '启动时间': now, '记录数': get_behavior_count()})
    print(f'后台模式 PID: {os.getpid()}')
    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        cmd_stop()


# ---- 命令行入口 ----

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        cmds = {
            'start': cmd_start, 'stop': cmd_stop, 'status': cmd_status,
            'analyze': cmd_analyze, 'detach': cmd_detach,
            'pause': cmd_pause, 'resume': cmd_resume,
        }
        fn = cmds.get(cmd)
        if fn:
            fn()
        else:
            print(f'未知命令: {cmd}')
            print('用法: python -m agent.agent [start|stop|pause|resume|status|analyze]')
    else:
        print('用法: python -m agent.agent [start|stop|status|analyze]')
