# anomaly_detection.py — 异常行为检测

import pandas as pd


def detect_duration_anomalies(df):
    all_anomalies = []
    for source in df['source_type'].unique():
        subset = df[df['source_type'] == source]
        durations = subset['duration_min']
        if len(durations) < 5:
            continue
        Q1 = durations.quantile(0.25)
        Q3 = durations.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR

        anomalies = subset[
            (subset['duration_min'] < lower_bound) |
            (subset['duration_min'] > upper_bound)
        ]
        if len(anomalies) > 0:
            print(f'{source}: 正常范围 [{lower_bound:.0f}, {upper_bound:.0f}] 分钟')
            for _, row in anomalies.iterrows():
                desc = f' - {row["description"]}' if pd.notna(row.get('description')) and row['description'] else ''
                print(f'  {row["event_date"]} {row["behavior_type"]}: {row["duration_min"]} 分钟{desc}')

    if all_anomalies:
        return pd.concat(all_anomalies, ignore_index=True)
    return pd.DataFrame()


def detect_behavior_change(df):
    df = df.copy()
    df['event_date'] = pd.to_datetime(df['event_date'])
    df['week'] = df['event_date'].dt.isocalendar().week
    weekly_stats = df.groupby(['source_type', 'week']).agg({
        'duration_min': 'sum', 'behavior_type': 'count'
    }).reset_index()
    weekly_stats.columns = ['source_type', '周数', '总耗时(分钟)', '活动次数']

    for source in df['source_type'].unique():
        s = weekly_stats[weekly_stats['source_type'] == source]
        if len(s) >= 2:
            last_week = s.iloc[-1]
            prev_week = s.iloc[-2]
            if prev_week['总耗时(分钟)'] == 0:
                continue
            change_pct = ((last_week['总耗时(分钟)'] - prev_week['总耗时(分钟)']) / prev_week['总耗时(分钟)'] * 100).round(1)
            flag = '变化较大' if abs(change_pct) > 30 else ''
            print(f'  {source}: {change_pct}% {flag}')

    return weekly_stats


def detect_time_slot_anomalies(df):
    df = df.copy()
    df['start_time'] = pd.to_datetime(df['start_time'], format='%H:%M:%S', errors='coerce')
    df['hour'] = df['start_time'].dt.hour
    night = df[df['hour'].between(23, 24) | df['hour'].between(0, 5)]
    if len(night) > 0:
        print(f'发现 {len(night)} 条深夜活动')
        for _, row in night.iterrows():
            print(f'  {row["event_date"]} {row["hour"]}:00 {row["behavior_type"]}')
    else:
        print('无深夜活动')
    return night


if __name__ == '__main__':
    df = pd.read_csv('data/user_behavior_clean.csv')
    from feature_engineering import extract_time_features
    df = extract_time_features(df)
    detect_duration_anomalies(df)
    detect_behavior_change(df)
    detect_time_slot_anomalies(df)
