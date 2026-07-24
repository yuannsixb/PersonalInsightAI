# recommendation.py — 自动化机会评估
#
# 只对 work/study 场景的活动做自动化评分
# 娱乐活动不参与自动化评估（游戏不需要自动化）

import pandas as pd


def calculate_automation_score(df):
    """
    只对工作和学习场景的活动做自动化评分
    娱乐和生活场景自动跳过
    """
    # 如果数据有 scene 列，只分析工作/学习类
    if 'scene' in df.columns:
        work_df = df[df['scene'].isin(['work', 'study'])].copy()
        if work_df.empty:
            print('没有工作和学习类活动，跳过自动化评估')
            return pd.DataFrame()
        df = work_df

    if 'frequency' not in df.columns:
        df['frequency'] = 7

    behavior_stats = df.groupby('behavior_type').agg({
        'frequency': 'mean', 'duration_min': 'mean', 'source_type': 'first'
    }).reset_index()

    repeatability_map = {'work': 8, 'study': 6, 'life': 5, 'leisure': 3, 'health': 4}
    standardization_map = {'work': 8, 'study': 5, 'life': 3, 'leisure': 2, 'health': 3}

    scores = []
    for _, row in behavior_stats.iterrows():
        name = row['behavior_type']
        source = row['source_type']
        freq = row['frequency']
        duration = row['duration_min']

        freq_score = min(freq / 7 * 10, 10)
        duration_score = min(duration / 120 * 10, 10)
        repeat_score = repeatability_map.get(source, 5)
        standard_score = standardization_map.get(source, 3)
        total = int(freq_score * duration_score * repeat_score * standard_score)

        scores.append({
            '行为': name, '来源': source,
            '频率分': round(freq_score, 1), '时长分': round(duration_score, 1),
            '重复性分': repeat_score, '标准化分': standard_score,
            '自动化价值评分': total
        })

    score_df = pd.DataFrame(scores).sort_values('自动化价值评分', ascending=False).reset_index(drop=True)

    if not score_df.empty:
        print('自动化价值评分排名（仅工作/学习类）:')
        for _, row in score_df.iterrows():
            print(f'  {row["行为"]}: {row["自动化价值评分"]} 分')
        top3 = score_df.head(3)
        print(f'Top 3: {", ".join(top3["行为"].tolist())}')
    else:
        print('没有可评估的活动')

    return score_df


def generate_recommendations(score_df):
    """根据评分生成建议"""
    recommendations = []
    tip_map = {
        'work': '建议用 Python + Pandas 自动处理，或接入 CI/CD 流程',
        'study': '建议用 Anki 等工具辅助，或写 API 自动整理笔记',
        'life': '建议用手机快捷指令或 IFTTT 自动化',
        'leisure': '可以设置时间提醒，或用聚合工具统一管理',
        'health': '可以用自动化脚本记录和提醒'
    }

    if score_df.empty:
        return [{'行为': '暂无', '评分': 0, '建议': '没有可自动化的工作/学习类活动'}]

    for _, row in score_df.head(5).iterrows():
        recommendations.append({
            '行为': row['行为'],
            '评分': row['自动化价值评分'],
            '建议': tip_map.get(row['来源'], '考虑用自动化脚本简化流程')
        })
    return recommendations


def get_leisure_summary(df):
    """统计娱乐活动的情况（不参与自动化评分，但展示给用户看）"""
    if 'scene' not in df.columns:
        return []
    leisure_df = df[df['scene'] == 'leisure']
    if leisure_df.empty:
        return []
    summary = leisure_df.groupby('behavior_type')['duration_min'].sum().sort_values(ascending=False)
    result = []
    for name, total in summary.items():
        result.append({'活动': name, '总耗时(分钟)': int(total), '小时': round(total / 60, 1)})
    return result


if __name__ == '__main__':
    df = pd.read_csv('data/user_behavior_clean.csv')
    score_df = calculate_automation_score(df)
    recs = generate_recommendations(score_df)
    for r in recs:
        print(f'{r["行为"]}: {r["建议"]}')

    print('\n娱乐活动统计:')
    leisure = get_leisure_summary(df)
    for l in leisure:
        print(f'  {l["活动"]}: {l["小时"]} 小时')
