# user_dictionary.py — 用户自定义分类规则管理
# v2.3.0 — 增加内存缓存，批量分类时一次性加载用户规则

from database.db import (
    add_user_rule, get_user_rules, load_user_rules_cache,
    update_user_rule, delete_user_rule
)

# 用户规则内存缓存
_user_rules_cache = None


def refresh_cache():
    """刷新用户规则内存缓存"""
    global _user_rules_cache
    _user_rules_cache = load_user_rules_cache()


def get_cached_rules():
    """获取用户规则缓存（首次自动加载）"""
    global _user_rules_cache
    if _user_rules_cache is None:
        _user_rules_cache = load_user_rules_cache()
    return _user_rules_cache


def add_rule(app_name, scene, window_title_keyword='', domain=''):
    """添加规则并刷新缓存"""
    add_user_rule(app_name, scene, window_title_keyword, domain)
    refresh_cache()


def delete_rule(rule_id):
    """删除规则并刷新缓存"""
    delete_user_rule(rule_id)
    refresh_cache()


def update_rule(rule_id, new_scene):
    """修改规则并刷新缓存"""
    update_user_rule(rule_id, new_scene)
    refresh_cache()


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
