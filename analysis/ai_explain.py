# ai_explain.py — AI 解释层
# 所有统计指标由 Pandas/SQLite 计算，AI 只负责生成自然语言

import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def get_ai_client():
    api_key = os.getenv('AI_API_KEY')
    base_url = os.getenv('AI_BASE_URL', 'https://api.deepseek.com')
    model = os.getenv('AI_MODEL', 'deepseek-v4-flash')
    if not api_key:
        return None, None
    return OpenAI(api_key=api_key, base_url=base_url), model


def _call(prompt, max_tokens=600):
    """调用 LLM，返回文本"""
    client, model = get_ai_client()
    if not client:
        return None
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f'（AI 调用失败: {e}）'


def _wrap(data, instruction):
    """把数据和指令拼成 prompt"""
    return f"""你是一个用户行为分析助手。请根据以下数据回答问题。
数据全部来自真实的本地采集，你只能基于数据回答，不能自行编造数字。

数据：
{json.dumps(data, ensure_ascii=False, indent=2)}

{instruction}

要求：
- 用中文回答，自然口语化
- 只说事实，不要用"根据数据显示"这种废话开头
- 不要编造数据中没有的信息
- 控制在 150 字以内"""


def ai_daily_insight(data):
    """今日洞察"""
    instruction = """请根据今日数据生成一段今日行为分析。
分析内容包括：
1. 今天的整体情况（总时长、记录数）
2. 效率表现（和昨天对比）
3. 时间分配特点
4. 值得注意的行为
5. 一个小建议

写一段连贯的文字，不要分点。"""
    return _call(_wrap(data, instruction))


def ai_optimization_advice(data):
    """个性化优化建议"""
    apps = data.get('today', {}).get('top_apps', [])
    if not apps:
        apps = data.get('weekly', {}).get('top_apps', [])
    apps_str = json.dumps(apps, ensure_ascii=False, indent=2)

    instruction = f"""以下是用户今天使用的主要软件及场景：
{apps_str}

请为每个软件生成一条简短、有针对性的优化建议。

要求：
- 工作类软件：侧重效率提升（脚本、模板、快捷键）
- 学习类软件：侧重学习方法、复习节奏
- 娱乐类软件：侧重时间管理，不要提"自动化"
- 生活/沟通类软件：可以说"无明显优化空间"
- 同类软件不要用相同文案

每行格式：
- 软件名: 建议内容"""
    return _call(_wrap(data, instruction))


def ai_weekly_report(data):
    """周报"""
    instruction = """请根据最近 7 天数据生成一段本周总结。

内容：
1. 本周总体情况
2. 工作和学习的变化趋势
3. 娱乐时间的分布
4. 效率表现
5. 下周建议

写一段连贯的文字，不要分点。"""
    return _call(_wrap(data, instruction))


def ai_trend_analysis(data):
    """趋势分析"""
    trend = data.get('daily_trend', [])
    trend_str = json.dumps(trend, ensure_ascii=False, indent=2)

    instruction = f"""以下是最近 7 天每日效率指数和场景时长趋势：
{trend_str}

请分析：
1. 效率变化趋势（上升/下降/波动）
2. 工作、学习、娱乐的时间变化
3. 哪天表现最好/最差
4. 原因推测

写一段连贯的文字，不要分点。"""
    return _call(_wrap(data, instruction))


def ai_user_profile(data):
    """用户画像"""
    instruction = """请根据最近 7 天的数据总结用户的行为画像。

画像类型可从以下选择：
- 持续学习型（学习时间多且稳定）
- 开发工作型（工作时间占主导）
- 夜间高效型（效率集中在晚上）
- 娱乐平衡型（娱乐和工作/学习时间平衡）
- 需要调整型（娱乐过多或效率偏低）

请说明判断依据和一句话建议。"""
    return _call(_wrap(data, instruction), max_tokens=400)


def ai_ask(question, data):
    """问答入口"""
    instruction = f"""用户提问：{question}

请根据以上数据回答用户的问题。
- 只能基于数据中的数字回答
- 如果数据不足以回答，说"数据不足以分析这个问题"
- 回答要具体、有数据支撑
- 不要编造"""
    return _call(_wrap(data, instruction))
