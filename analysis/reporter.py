# reporter.py — 洞察报告 v2.1.2
#
# 优化：
#   1. 不再 SELECT * 全表扫，按时间范围查询
#   2. 全部字段统一叫 scene
#   3. 各场景来源明细（GROUP BY scene, process_name）

import os
import pandas as pd
from datetime import datetime, timedelta
from database.db import get_conn, save_report


def build_report():
    """生成洞察报告，只分析最近 7 天数据"""
    today = datetime.now().strftime('%Y-%m-%d')
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    conn = get_conn()
    # 只查最近 7 天，不走全表
    rows = conn.execute(
        'SELECT id, event_date, start_time, duration_min, process_name, scene, window_title '
        'FROM behavior_log WHERE event_date >= ? ORDER BY id',
        (seven_days_ago,)
    ).fetchall()
    conn.close()

    if len(rows) < 5:
        return '数据不足（少于 5 条），继续采集中...'

    df = pd.DataFrame([dict(r) for r in rows])
    total_min = df['duration_min'].sum()
    total_hours = total_min / 60

    # 今日数据单独统计
    df_today = df[df['event_date'] == today]

    # ---- 按场景统计 ----
    scene_stats = df.groupby('scene').agg(
        时长_分钟=('duration_min', 'sum'),
        次数=('id', 'count')
    ).reset_index()
    scene_stats['时长_小时'] = (scene_stats['时长_分钟'] / 60).round(1)
    scene_stats['占比'] = (scene_stats['时长_分钟'] / total_min * 100).round(1)
    scene_stats = scene_stats.sort_values('时长_分钟', ascending=False)

    # ---- 按场景+应用统计 ----
    detail = df.groupby(['scene', 'process_name']).agg(
        时长_分钟=('duration_min', 'sum'),
        次数=('id', 'count')
    ).reset_index().sort_values(['scene', '时长_分钟'], ascending=[True, False])

    # 场景名称
    names = {'work': '工作', 'study': '学习', 'leisure': '娱乐',
             'life': '生活', 'browser': '浏览', 'unknown': '待分类'}

    # ---- 组装报告 ----
    lines = []
    lines.append('PersonalInsightAI 洞察报告')
    lines.append('=' * 40)
    lines.append(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append(f'范围: {seven_days_ago} ~ {today}  |  {len(df)} 条记录  |  共 {total_hours:.1f}h')
    lines.append('')

    # ① 场景分布
    lines.append('【场景分布（7天）】')
    for _, row in scene_stats.iterrows():
        name = names.get(row['scene'], row['scene'])
        bar = '#' * int(row['占比'] / 5) + '.' * (20 - int(row['占比'] / 5))
        lines.append(f'  {name:4s} [{bar}] {row["占比"]}%  ({row["时长_小时"]}h)')

    lines.append('')

    # ② 效率分析
    work_h = scene_stats[scene_stats['scene'] == 'work']['时长_小时'].sum() if 'work' in scene_stats['scene'].values else 0
    study_h = scene_stats[scene_stats['scene'] == 'study']['时长_小时'].sum() if 'study' in scene_stats['scene'].values else 0
    leisure_h = scene_stats[scene_stats['scene'] == 'leisure']['时长_小时'].sum() if 'leisure' in scene_stats['scene'].values else 0
    unknown_h = scene_stats[scene_stats['scene'] == 'unknown']['时长_小时'].sum() if 'unknown' in scene_stats['scene'].values else 0

    lines.append('【效率分析】')
    lines.append(f'  工作: {work_h:.1f}h  |  学习: {study_h:.1f}h  |  娱乐: {leisure_h:.1f}h')
    eff = ((work_h + study_h) / max(total_hours, 0.1) * 100)
    lines.append(f'  效率指数: {eff:.0f}')
    if unknown_h > 0:
        lines.append(f'  待分类: {unknown_h:.1f}h')
    lines.append('')

    # ③ 今日速览
    if not df_today.empty:
        today_min = df_today['duration_min'].sum()
        today_hours = today_min / 60
        today_scenes = df_today.groupby('scene')['duration_min'].sum()
        lines.append('【今日速览】')
        lines.append(f'  今日记录: {len(df_today)} 条  |  共 {today_hours:.1f}h')
        for scene_key in ['work', 'study', 'leisure', 'life', 'unknown']:
            if scene_key in today_scenes.index:
                name = names.get(scene_key, scene_key)
                h = today_scenes[scene_key] / 60
                lines.append(f'  · {name}: {h:.1f}h')
        lines.append('')

    # ④ 各场景来源分析
    lines.append('【各场景来源】（7天）')
    for scene_key in ['work', 'study', 'leisure', 'life', 'unknown']:
        sub = detail[detail['scene'] == scene_key]
        if sub.empty:
            continue
        name = names.get(scene_key, scene_key)
        total = sub['时长_分钟'].sum() / 60
        lines.append(f'  {name}（{total:.1f}h）:')
        for _, row in sub.head(4).iterrows():
            app = row['process_name'].replace('.exe', '')
            lines.append(f'    · {app}  {row["时长_分钟"]/60:.1f}h（{row["次数"]}次）')
    lines.append('')

    # ⑤ 自动化建议（仅工作/学习，高频+长耗时）
    lines.append('【自动化建议】')
    work_study = df[df['scene'].isin(['work', 'study'])].copy()
    if len(work_study) >= 5:
        app_stats = work_study.groupby('process_name').agg(
            次数=('id', 'count'),
            总时长=('duration_min', 'sum')
        ).reset_index().sort_values(['次数', '总时长'], ascending=False)
        suggs = app_stats[(app_stats['次数'] >= 5) & (app_stats['总时长'] >= 30)].head(3)
        if not suggs.empty:
            for _, row in suggs.iterrows():
                lines.append(f'  · {row["process_name"]}: {row["次数"]}次, {row["总时长"]:.0f}分钟 — 考虑自动化')
        else:
            lines.append('  暂无明显可优化的重复性工作。')
    else:
        lines.append('  数据不足（工作/学习需 ≥ 5 条）。')

    # ⑥ 娱乐提醒
    if leisure_h > 3:
        lines.append(f'\n最近 7 天娱乐时间: {leisure_h:.1f}h')
    elif leisure_h == 0:
        lines.append('\n没有检测到娱乐活动，注意休息')

    lines.append('')
    lines.append('=' * 40)
    report = '\n'.join(lines)

    save_report('auto', report)
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'reports',
        f'insight_{datetime.now().strftime("%Y%m%d_%H%M")}.txt'
    )
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f'报告已生成: {report_path}')
    return report


def build_insight_json():
    """生成完整统计 JSON，供 AI 消费"""
    today = datetime.now().strftime('%Y-%m-%d')
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    conn = get_conn()
    rows_7d = conn.execute(
        'SELECT id, event_date, start_time, duration_min, process_name, scene, window_title '
        'FROM behavior_log WHERE event_date >= ? ORDER BY id',
        (seven_days_ago,)
    ).fetchall()
    rows_30d = conn.execute(
        'SELECT id, event_date, start_time, duration_min, process_name, scene, window_title '
        'FROM behavior_log WHERE event_date >= ? ORDER BY id',
        (thirty_days_ago,)
    ).fetchall()
    conn.close()

    if len(rows_7d) < 5:
        return None

    df7 = pd.DataFrame([dict(r) for r in rows_7d])
    df30 = pd.DataFrame([dict(r) for r in rows_30d])
    df_today = df7[df7['event_date'] == today].copy()
    df_yesterday = df7[df7['event_date'] == (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')].copy()

    names = {'work': '工作', 'study': '学习', 'leisure': '娱乐',
             'life': '生活', 'browser': '浏览', 'unknown': '待分类'}

    def scene_hours(d, scene):
        return round(d[d['scene'] == scene]['duration_min'].sum() / 60, 1)

    def top_apps(d, n=5):
        if d.empty:
            return []
        apps = d.groupby('process_name').agg(
            hours=('duration_min', lambda x: round(x.sum()/60, 1)),
            scene=('scene', 'first'),
            switches=('id', 'count')
        ).reset_index().sort_values('hours', ascending=False).head(n)
        return [
            {
                'name': r['process_name'].replace('.exe', ''),
                'hours': r['hours'],
                'scene': names.get(r['scene'], r['scene']),
                'switches': int(r['switches'])
            }
            for _, r in apps.iterrows()
        ]

    def daily_trend(d):
        d = d.copy()
        d['event_date'] = pd.to_datetime(d['event_date'])
        trend = d.groupby('event_date').agg(
            total=('duration_min', 'sum'),
            work=('duration_min', lambda x: x[d.loc[x.index, 'scene'] == 'work'].sum()),
            study=('duration_min', lambda x: x[d.loc[x.index, 'scene'] == 'study'].sum()),
            leisure=('duration_min', lambda x: x[d.loc[x.index, 'scene'] == 'leisure'].sum()),
        ).reset_index()
        trend['efficiency'] = round((trend['work'] + trend['study']) / trend['total'] * 100, 1)
        trend['date'] = trend['event_date'].dt.strftime('%Y-%m-%d')
        return trend[['date', 'efficiency', 'work', 'study', 'leisure']].to_dict('records')

    # 今日
    today_h = df_today['duration_min'].sum() / 60 if not df_today.empty else 0
    today_eff = round((scene_hours(df_today, 'work') + scene_hours(df_today, 'study')) / max(today_h, 0.1) * 100, 1)

    # 7天
    total_h_7d = df7['duration_min'].sum() / 60
    work_h_7d = scene_hours(df7, 'work')
    study_h_7d = scene_hours(df7, 'study')
    leisure_h_7d = scene_hours(df7, 'leisure')
    eff_7d = round((work_h_7d + study_h_7d) / max(total_h_7d, 0.1) * 100, 1)

    # 昨天对比
    yesterday_h = df_yesterday['duration_min'].sum() / 60 if not df_yesterday.empty else 0
    yesterday_eff = round((scene_hours(df_yesterday, 'work') + scene_hours(df_yesterday, 'study')) / max(yesterday_h, 0.1) * 100, 1) if not df_yesterday.empty else None

    # 30天
    total_h_30d = df30['duration_min'].sum() / 60
    work_h_30d_v2 = scene_hours(df30, 'work') if len(df30) <= len(df7) else scene_hours(df30, 'work')
    study_h_30d = scene_hours(df30, 'study')
    leisure_h_30d = scene_hours(df30, 'leisure')

    # 14天趋势（用于对比）
    fourteen_days_ago = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    conn2 = get_conn()
    rows_14d = conn2.execute(
        'SELECT event_date, duration_min, scene '
        'FROM behavior_log WHERE event_date >= ? ORDER BY id',
        (fourteen_days_ago,)
    ).fetchall()
    conn2.close()
    if rows_14d:
        df14 = pd.DataFrame([dict(r) for r in rows_14d])
        df14['event_date'] = pd.to_datetime(df14['event_date'])
        # 前7天 vs 后7天
        mid = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        earlier = df14[df14['event_date'] < mid]
        later = df14[df14['event_date'] >= mid]
        study_trend = {
            'earlier_7d_h': round(earlier[earlier['scene'] == 'study']['duration_min'].sum() / 60, 1),
            'later_7d_h': round(later[later['scene'] == 'study']['duration_min'].sum() / 60, 1),
        }
    else:
        study_trend = {}

    result = {
        'today': {
            'date': today,
            'total_records': int(len(df_today)),
            'total_hours': round(today_h, 1),
            'efficiency': today_eff,
            'work_hours': scene_hours(df_today, 'work'),
            'study_hours': scene_hours(df_today, 'study'),
            'leisure_hours': scene_hours(df_today, 'leisure'),
            'life_hours': scene_hours(df_today, 'life'),
            'unknown_hours': scene_hours(df_today, 'unknown'),
            'top_apps': top_apps(df_today),
            'switch_count': int(len(df_today)),
        },
        'yesterday': {
            'efficiency': yesterday_eff,
            'total_hours': round(yesterday_h, 1),
            'work_hours': scene_hours(df_yesterday, 'work'),
            'study_hours': scene_hours(df_yesterday, 'study'),
            'leisure_hours': scene_hours(df_yesterday, 'leisure'),
        } if not df_yesterday.empty else None,
        'weekly': {
            'total_records': int(len(df7)),
            'total_hours': round(total_h_7d, 1),
            'avg_daily_hours': round(total_h_7d / max(df7['event_date'].nunique(), 1), 1),
            'efficiency': eff_7d,
            'work_hours': work_h_7d,
            'study_hours': study_h_7d,
            'leisure_hours': leisure_h_7d,
            'life_hours': scene_hours(df7, 'life'),
            'unknown_hours': scene_hours(df7, 'unknown'),
            'top_apps': top_apps(df7, 8),
        },
        'daily_trend': daily_trend(df7),
        'thirty_days': {
            'total_hours': round(total_h_30d, 1),
            'study_hours': study_h_30d,
        },
        'study_trend': study_trend,
    }
    return result


if __name__ == '__main__':
    print(build_report())
