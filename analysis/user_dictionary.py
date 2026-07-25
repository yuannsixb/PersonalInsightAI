# user_dictionary.py — 用户自定义分类规则管理
# v2.3.1 — 修改词典后自动重算所有历史数据

from database.db import (
    add_user_rule, get_user_rules, load_user_rules_cache,
    update_user_rule, delete_user_rule, get_conn
)

# 用户规则内存缓存: (simple_dict, keyword_list)
_simple_cache = None
_keyword_cache = None


def refresh_cache():
    """刷新用户规则内存缓存"""
    global _simple_cache, _keyword_cache
    _simple_cache, _keyword_cache = load_user_rules_cache()


def get_cached_rules():
    """获取用户规则缓存（首次自动加载）
    返回 (simple_dict, keyword_list)
    """
    global _simple_cache, _keyword_cache
    if _simple_cache is None:
        _simple_cache, _keyword_cache = load_user_rules_cache()
    return _simple_cache, _keyword_cache


def add_rule(app_name, scene, window_title_keyword='', domain=''):
    """添加规则并刷新缓存，重算历史数据"""
    add_user_rule(app_name, scene, window_title_keyword, domain)
    refresh_cache()
    reclassify_all()


def delete_rule(rule_id):
    """删除规则并刷新缓存，重算历史数据"""
    delete_user_rule(rule_id)
    refresh_cache()
    reclassify_all()


def update_rule(rule_id, new_scene):
    """修改规则并刷新缓存，重算历史数据"""
    update_user_rule(rule_id, new_scene)
    refresh_cache()
    reclassify_all()


def reclassify_all():
    """根据当前用户规则 + 系统分类器，重新分类所有历史数据"""
    from analysis.scene_classifier import classify, clear_cache

    simple, keyword = get_cached_rules()
    rules_cache = (simple, keyword)

    conn = get_conn()

    # 读取所有记录
    rows = conn.execute(
        'SELECT id, process_name, window_title FROM behavior_log'
    ).fetchall()

    if not rows:
        return

    clear_cache()
    updated = 0
    for r in rows:
        rec_id = r['id']
        pname = r['process_name'] or ''
        wtitle = r['window_title'] or ''
        new_scene = classify(str(pname), str(wtitle), rules_cache)
        conn.execute(
            'UPDATE behavior_log SET scene = ? WHERE id = ?',
            (new_scene, rec_id)
        )
        updated += 1

    # 刷新每日汇总
    conn.execute('DELETE FROM daily_summary')
    conn.execute('''
        INSERT INTO daily_summary (summary_date, scene, total_min, record_count)
        SELECT event_date, scene, SUM(duration_min), COUNT(*)
        FROM behavior_log GROUP BY event_date, scene
    ''')

    conn.commit()
    print(f'[知识库] 重分类完成: {updated} 条记录')


def batch_classify_with_user_rules(df):
    """
    使用用户规则 + 系统分类器批量分类。
    一次性加载用户规则到内存，减少数据库查询。
    """
    from analysis.scene_classifier import batch_classify, clear_cache

    if df.empty:
        return df

    # 获取用户规则缓存
    rules_cache = get_cached_rules()

    # 清除旧的分类缓存，让新规则生效
    clear_cache()

    # 传入用户规则缓存，分类器直接查内存
    return batch_classify(df, rules_cache)
