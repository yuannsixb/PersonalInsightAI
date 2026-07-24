# feature_engineering.py — 特征工程

import pandas as pd


def extract_time_features(df):
    df = df.copy()
    df['event_date'] = pd.to_datetime(df['event_date'])
    df['weekday'] = df['event_date'].dt.dayofweek
    df['is_weekend'] = df['weekday'].apply(lambda x: 1 if x >= 5 else 0)
    df['month'] = df['event_date'].dt.month
    df['start_time'] = pd.to_datetime(df['start_time'], format='%H:%M:%S', errors='coerce')
    df['hour'] = df['start_time'].dt.hour

    def time_period(h):
        if pd.isna(h):
            return '未知'
        if h < 12:
            return '上午'
        elif h < 14:
            return '中午'
        elif h < 18:
            return '下午'
        return '晚上'

    df['time_period'] = df['hour'].apply(time_period)
    print(f'新增特征: weekday, is_weekend, month, hour, time_period')
    return df


def label_duration_level(df):
    df = df.copy()
    bins = [0, 30, 60, 120, 9999]
    labels = ['短(<30min)', '中(30-60min)', '长(1-2h)', '超长(>2h)']
    df['duration_level'] = pd.cut(df['duration_min'], bins=bins, labels=labels)
    print(f'时长分段:')
    print(df['duration_level'].value_counts())
    return df


if __name__ == '__main__':
    df = pd.read_csv('data/user_behavior_clean.csv')
    df = extract_time_features(df)
    df = label_duration_level(df)
    print(f'特征工程完成: {df.shape[0]} 行, {df.shape[1]} 列')
