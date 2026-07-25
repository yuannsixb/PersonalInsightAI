# user_profile.py — 用户画像分析

import pandas as pd


def calculate_source_ratios(df):
    source_time = df.groupby('source_type')['duration_min'].sum()
    total_time = source_time.sum()
    ratios = (source_time / total_time * 100).round(1)
    print('时间分配:')
    for source, ratio in ratios.items():
        hours = source_time[source] / 60
        print(f'  {source}: {ratio}%（约 {hours:.0f} 小时）')
    return ratios.to_dict()


def classify_user_type(ratios):
    if not ratios:
        return '未知类型'
    top_source = max(ratios, key=ratios.get)
    top_ratio = ratios[top_source]
    profile_map = {
        'work': '效率优化型', 'study': '知识学习型',
        'leisure': '娱乐消费型', 'life': '生活平衡型', 'health': '健康自律型'
    }
    profile = profile_map.get(top_source, '综合型')
    print(f'用户类型: {profile}（{top_source} 占比最高 {top_ratio}%）')
    return profile


def calculate_scores(df, ratios):
    scores = {}

    work_ratio = ratios.get('work', 0)
    work_df = df[df['source_type'] == 'work']
    if len(work_df) > 0 and 'hour' in df.columns:
        regular_count = work_df[work_df['hour'].between(8, 18)].shape[0]
        work_regular = regular_count / len(work_df) * 100
    else:
        work_regular = 0
    scores['效率指数'] = round(min(work_ratio * 1.5 + work_regular * 0.3, 100), 1)

    study_ratio = ratios.get('study', 0)
    scores['学习指数'] = round(min(study_ratio * 2.5, 100), 1)

    useful_time = ratios.get('work', 0) + ratios.get('study', 0)
    scores['时间管理指数'] = round(min(useful_time * 1.5, 100), 1)

    print(f'效率指数: {scores["效率指数"]} 分')
    print(f'学习指数: {scores["学习指数"]} 分')
    print(f'时间管理指数: {scores["时间管理指数"]} 分')
    return scores


def generate_profile(df):
    ratios = calculate_source_ratios(df)
    profile_type = classify_user_type(ratios)
    scores = calculate_scores(df, ratios)
    return {
        '用户类型': profile_type,
        '时间分配': ratios,
        '效率指数': scores.get('效率指数', 0),
        '学习指数': scores.get('学习指数', 0),
        '时间管理指数': scores.get('时间管理指数', 0)
    }


if __name__ == '__main__':
    df = pd.read_csv('data/user_behavior_clean.csv')
    from feature_engineering import extract_time_features
    df = extract_time_features(df)
    profile = generate_profile(df)
    print(f'用户画像: {profile}')
