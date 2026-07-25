# data_cleaning.py — 数据清洗

import pandas as pd


def load_data(filepath='data/user_behavior.csv'):
    df = pd.read_csv(filepath)
    print(f'读取数据: {df.shape[0]} 行, {df.shape[1]} 列')
    return df


def inspect_data(df):
    report = {
        '原始行数': df.shape[0],
        '缺失值数量': int(df.isnull().sum().sum()),
        '重复行数': int(df.duplicated().sum())
    }
    print(f'缺失值: {report["缺失值数量"]} 个')
    print(f'重复行: {report["重复行数"]} 行')
    return report


def clean_data(df):
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    print(f'删除重复行: {removed} 行')

    for col in df.columns:
        missing_count = df[col].isnull().sum()
        if missing_count > 0:
            print(f'{col} 缺失: {missing_count} 个')

    if 'duration_min' in df.columns:
        df['duration_min'] = df['duration_min'].fillna(df['duration_min'].median())

    if 'frequency' in df.columns:
        df['frequency'] = pd.to_numeric(df['frequency'], errors='coerce')
        df['frequency'] = df['frequency'].fillna(df['frequency'].mean())

    if 'description' in df.columns:
        df['description'] = df['description'].fillna('')

    if 'event_date' in df.columns:
        df['event_date'] = pd.to_datetime(df['event_date'])

    print(f'清洗完成: {df.shape[0]} 行')
    return df


def save_clean_data(df, filepath='data/user_behavior_clean.csv'):
    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    print(f'已保存到 {filepath}')


if __name__ == '__main__':
    df_raw = load_data()
    inspect_data(df_raw)
    df_clean = clean_data(df_raw)
    save_clean_data(df_clean)
