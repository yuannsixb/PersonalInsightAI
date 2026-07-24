# app.py — PersonalInsightAI Dashboard
# v2.3.0

import streamlit as st
import pandas as pd
import altair as alt
import json, os
from datetime import datetime, timedelta, date

st.set_page_config(page_title='PersonalInsightAI', layout='wide')

# ---- 初始化 ----
if 'page' not in st.session_state: st.session_state.page = 'dashboard'
if 'data_version' not in st.session_state: st.session_state.data_version = 0

from database.db import init_db, get_conn, get_config, get_behavior_count
from analysis.reporter import build_insight_json
from analysis.ai_explain import ai_daily_insight, ai_optimization_advice, ai_weekly_report, ai_trend_analysis, ai_user_profile, ai_ask
init_db()

scene_names = {'work': '工作', 'study': '学习', 'leisure': '娱乐',
               'life': '生活', 'browser': '浏览', 'unknown': '待分类'}
scene_colors = {'工作': '#1f77b4', '学习': '#2ca02c', '娱乐': '#ff7f0e',
                '生活': '#9467bd', '浏览': '#7f7f7f', '待分类': '#d3d3d3'}
today_str = datetime.now().strftime('%Y-%m-%d')


# ---- 数据加载（手动缓存 + 版本号控制）----
def _load_data_internal():
    from analysis.user_dictionary import batch_classify_with_user_rules
    conn = get_conn()
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    rows = conn.execute('''
        SELECT id, event_date, start_time, duration_min,
               process_name, scene, window_title
        FROM behavior_log WHERE event_date >= ? ORDER BY id DESC
    ''', (seven_days_ago,)).fetchall()
    if not rows:
        return None
    df = pd.DataFrame([dict(r) for r in rows])
    df = batch_classify_with_user_rules(df)
    df['event_date'] = pd.to_datetime(df['event_date'])
    df['时长_小时'] = df['duration_min'] / 60
    df['场景名'] = df['scene'].map(scene_names).fillna(df['scene'])
    return df


def get_data():
    if 'cached_df' not in st.session_state or st.session_state.get('cached_ver', -1) != st.session_state.data_version:
        st.session_state.cached_df = _load_data_internal()
        st.session_state.cached_ver = st.session_state.data_version
    return st.session_state.cached_df


def refresh_data():
    """显式刷新：版本号+1 + 清除缓存"""
    st.session_state.data_version += 1
    if 'cached_df' in st.session_state:
        del st.session_state.cached_df
    if 'cached_ver' in st.session_state:
        del st.session_state.cached_ver


# 浏览器中文名 + 进程名显示
_BROWSER_SHORT = {'msedge.exe':'Edge','chrome.exe':'Chrome','firefox.exe':'Firefox','edge.exe':'Edge'}
_KNOWN_APPS = {'weixin.exe':'微信','wxwork.exe':'企业微信','dingtalk.exe':'钉钉',
               'feishu.exe':'飞书','tencentmeeting.exe':'腾讯会议','zoom.exe':'Zoom',
               'cloudmusic.exe':'网易云音乐','steam.exe':'Steam','code.exe':'VS Code',
               'wechat.exe':'微信','qq.exe':'QQ','explorer.exe':'文件管理器',
               'potplayer.exe':'PotPlayer','notepad++.exe':'Notepad++','idea64.exe':'IntelliJ',
               'pycharm64.exe':'PyCharm','sublime_text.exe':'Sublime','git-bash.exe':'Git Bash'}


def app_name(proc, title=''):
    """显示友好的应用名，浏览器显示为 Edge.ChatGPT 形式"""
    p = (proc or '').lower().strip()
    t = (title or '').strip()
    # 去掉标题里的 Windows 分组后缀
    import re
    t = re.split(r'[和与]另', t)[0].strip()
    if p in _BROWSER_SHORT:
        browser = _BROWSER_SHORT[p]
        if t:
            page = t.split(' - ')[0].split(' \u2014 ')[0].split(' | ')[0].strip()[:20]
            return f'{browser}.{page}' if page else browser
        return browser
    return _KNOWN_APPS.get(p, proc.replace('.exe','') if proc else '')


def calc_scene_stats(data):
    stats = data.groupby('scene').agg(时长_分钟=('duration_min','sum'),次数=('id','count')).reset_index()
    stats['场景名'] = stats['scene'].map(scene_names).fillna(stats['scene'])
    stats['时长_小时'] = (stats['时长_分钟']/60).round(1)
    t = stats['时长_分钟'].sum()
    stats['占比'] = (stats['时长_分钟']/t*100).round(1) if t>0 else 0
    return stats.sort_values('时长_分钟', ascending=False)


def eff_label(score):
    return '优秀' if score>=80 else ('良好' if score>=50 else '待改善')


# ---- 侧边栏 ----
with st.sidebar:
    st.title('PersonalInsightAI')
    st.caption('v2.3.0')
    if st.button('数据面板', use_container_width=True, type='secondary' if st.session_state.page!='dashboard' else 'primary'):
        st.session_state.page='dashboard'; st.rerun()
    if st.button('我的知识库', use_container_width=True, type='secondary' if st.session_state.page!='knowledge' else 'primary'):
        st.session_state.page='knowledge'; st.rerun()
    st.divider()
    ai_key = os.getenv('AI_API_KEY')
    if ai_key:
        st.info('AI 已连接')
    else:
        st.warning('AI 未配置')
    st.divider(); st.write('采集控制')
    from config import PAUSE_FILE, STATUS_FILE
    sd = {}
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE) as f: sd = json.load(f)
    running = sd.get('状态')=='运行中'
    paused = os.path.exists(PAUSE_FILE)
    if running:
        st.success('运行中' if not paused else '运行中（已暂停）')
        st.caption(f"记录: {sd.get('记录数', get_behavior_count())} 条")
        if paused:
            if st.button('恢复采集', use_container_width=True):
                if os.path.exists(PAUSE_FILE): os.remove(PAUSE_FILE); st.rerun()
        else:
            if st.button('暂停采集', use_container_width=True):
                os.makedirs(os.path.dirname(PAUSE_FILE), exist_ok=True)
                with open(PAUSE_FILE,'w') as f: f.write('paused'); st.rerun()
    else:
        st.info('未运行'); st.caption('启动: python agent.py detach')
    st.divider(); st.write('所有数据存储在本地')

# ============================================================
# 知识库页面
# ============================================================
if st.session_state.page == 'knowledge':
    st.subheader('我的知识库')
    st.caption('修改规则后自动生效，所有历史数据重新分类')
    from database.db import get_user_rules, add_user_rule as db_add_rule, update_user_rule as db_upd_rule, delete_user_rule as db_del_rule

    col_new, col_stats = st.columns([2, 1])
    with col_new:
        with st.container(border=True):
            st.write('**添加新规则**')
            # 获取今日进程列表：普通进程按名，浏览器按窗口标题细分
            _rows = get_conn().execute(
                "SELECT process_name, window_title FROM behavior_log WHERE event_date = ?",
                (today_str,)
            ).fetchall()
            _seen = set()
            _options = []
            import re as _re
            for r in _rows:
                p = r['process_name']
                t = r['window_title'] or ''
                t_clean = _re.split(r'[和与]另', t)[0].strip()
                display = app_name(p, t_clean)
                if display not in _seen:
                    _seen.add(display)
                    _options.append({'display': display, 'proc': p, 'title': t_clean})
            _options.sort(key=lambda x: x['display'])
            _options.insert(0, {'display': '-- 请选择一个应用 --', 'proc': '', 'title': ''})
            with st.form('add_rule_form', clear_on_submit=True):
                _idx = st.selectbox('选择进程', range(len(_options)),
                    format_func=lambda i: _options[i]['display'], key='asel')
                new_app = _options[_idx]['proc']
                # 从标题提取关键词：取第一个有用词
                _raw_title = _options[_idx]['title']
                _kw = _raw_title.split(' - ')[0].split(' \u2014 ')[0].split(' | ')[0].strip() if _raw_title else ''
                new_kw = _kw if _kw != new_app.replace('.exe','') else ''
                new_scene = st.selectbox('分类', ['work','study','leisure','life'],
                    format_func=lambda x:{'work':'工作','study':'学习','leisure':'娱乐','life':'生活'}.get(x,x))
                if st.form_submit_button('保存规则', use_container_width=True) and new_app:
                    from analysis.user_dictionary import refresh_cache
                    db_add_rule(new_app.lower(), new_scene, new_kw.strip())
                    refresh_cache()
                    refresh_data()
                    st.rerun()

    with col_stats:
        from database.db import get_user_rules_count
        with st.container(border=True):
            st.write('**知识库统计**')
            st.metric('自定义规则', f'{get_user_rules_count()} 条')

    st.divider()
    rules = get_user_rules()
    if rules:
        lbl = {'work':'工作','study':'学习','leisure':'娱乐','life':'生活','unknown':'待分类','browser':'浏览'}
        for r in rules:
            cols = st.columns([3,1,1,0.5,0.5])
            cols[0].write(f'**{r["app_name"]}**'+(f' ({r["window_title_keyword"]})' if r['window_title_keyword'] else ''))
            cols[1].write(lbl.get(r['scene'],r['scene']))
            cols[2].caption(r['create_time'][:10] if r['create_time'] else '')
            if cols[3].button('改', key=f'er_{r["id"]}'): st.session_state.editing_rule=r; st.rerun()
            if cols[4].button('删', key=f'dr_{r["id"]}'):
                from analysis.user_dictionary import refresh_cache
                db_del_rule(r['id']); refresh_cache(); refresh_data(); st.rerun()
        if 'editing_rule' in st.session_state:
            r = st.session_state.editing_rule
            with st.container(border=True):
                st.write(f'**修改规则：{r["app_name"]}**')
                ns = st.selectbox('新分类', ['work','study','leisure','life'],
                    index=['work','study','leisure','life'].index(r['scene']) if r['scene'] in ['work','study','leisure','life'] else 0,
                    format_func=lambda x:{'work':'工作','study':'学习','leisure':'娱乐','life':'生活'}.get(x,x), key='re_scene')
                c1,c2 = st.columns(2)
                if c1.button('保存修改', use_container_width=True):
                    from analysis.user_dictionary import refresh_cache
                    db_upd_rule(r['id'], ns); refresh_cache(); refresh_data()
                    del st.session_state.editing_rule; st.rerun()
                if c2.button('取消', use_container_width=True): del st.session_state.editing_rule; st.rerun()
    else:
        st.info('还没有自定义规则。')
    st.divider()
    if st.button('返回数据面板', use_container_width=True): st.session_state.page='dashboard'; st.rerun()
    st.stop()

# ============================================================
# 数据面板
# ============================================================
raw_df = get_data()
if raw_df is None:
    st.info('暂无数据。启动采集：python agent.py start'); st.stop()

df = raw_df.copy()
df_today = df[df['event_date']==today_str].copy()
df_today['显示名'] = df_today.apply(lambda r: app_name(r['process_name'], r.get('window_title','')), axis=1)
total_stats = calc_scene_stats(df)
today_stats = calc_scene_stats(df_today) if not df_today.empty else pd.DataFrame()

# ---- 1. 今日状态 ----
st.subheader('今日状态')
wh = today_stats[today_stats['scene']=='work']['时长_小时'].sum() if not today_stats.empty else 0
sh = today_stats[today_stats['scene']=='study']['时长_小时'].sum() if not today_stats.empty else 0
lh = today_stats[today_stats['scene']=='leisure']['时长_小时'].sum() if not today_stats.empty else 0
uh = today_stats[today_stats['scene']=='unknown']['时长_小时'].sum() if not today_stats.empty else 0
th = today_stats['时长_小时'].sum() if not today_stats.empty else 0
eff = ((wh+sh)/max(th,0.1)*100) if th>0 else 0
c1,c2,c3,c4,c5 = st.columns(5)
c1.metric('效率指数',f'{eff:.0f} ({eff_label(eff)})')
c2.metric('工作',f'{wh:.1f}h');c3.metric('学习',f'{sh:.1f}h')
c4.metric('娱乐',f'{lh:.1f}h');c5.metric('待分类',f'{uh:.1f}h')
if uh>0.5: st.caption(f'有 {uh:.1f}h 未分类，可在知识库添加规则')
elif th<0.5: st.caption('数据采集中...')
elif lh>wh+sh: st.caption(f'娱乐 {lh:.1f}h > 工作+学习 {wh+sh:.1f}h')
else: st.caption(f'工作 {wh:.1f}h / 学习 {sh:.1f}h / 娱乐 {lh:.1f}h')
if not df_today.empty:
    known = len(df_today[df_today['scene']!='unknown'])
    st.caption(f'今日: {len(df_today)} 条 | 已识别 {known} 条 | 识别率 {round(known/max(len(df_today),1)*100)}%')

# ---- 2. Top 5 ----
if not df_today.empty:
    st.subheader('今日 Top 5')
    for _, row in df_today.groupby('显示名').agg(时长=('duration_min','sum'),场景=('scene','first')).reset_index().sort_values('时长',ascending=False).head(5).iterrows():
        with st.container(border=True):
            ca,cb,cc = st.columns([2,1,1])
            ca.write(f'**{row["显示名"]}**')
            cb.write(f'{row["时长"]:.0f}分')
            cc.write(scene_names.get(row['场景'],row['场景']))

# ---- 3. 时间分布 ----
st.subheader('时间分布')
if not today_stats.empty:
    ca,cb = st.columns([2,1])
    bar = alt.Chart(today_stats).mark_bar().encode(
        x=alt.X('场景名',sort=None,axis=alt.Axis(labelAngle=0)), y='时长_小时',
        color=alt.Color('场景名',scale=alt.Scale(domain=list(scene_colors.keys()),range=list(scene_colors.values())))
    ).properties(height=200)
    ca.altair_chart(bar,use_container_width=True)
    cb.dataframe(today_stats[['场景名','时长_小时','占比','次数']].rename(columns={'时长_小时':'h','占比':'%','次数':'条'}),hide_index=True)
else: st.info('今日暂无数据')

# ---- 4. 各场景来源 ----
st.subheader('各场景来源')
if not df_today.empty:
    detail=df_today.groupby(['场景名','显示名']).agg(h=('duration_min',lambda x:round(x.sum()/60,1)),次=('id','count')).reset_index().sort_values(['场景名','h'],ascending=[True,False])
    for sk in ['work','study','leisure','life','browser','unknown']:
        sub=detail[detail['场景名']==scene_names.get(sk,sk)]
        if sub.empty: continue
        with st.container(border=True):
            st.write(f'**{scene_names.get(sk,sk)}**')
            for _,r in sub.head(5).iterrows(): st.write(f'{r["显示名"]}  {r["h"]}h ({r["次"]}次)')
else: st.info('暂无今日数据')

# ---- 5. 今日行为记录 ----
st.subheader('今日行为记录')
today_records = df_today.sort_values('start_time',ascending=False) if not df_today.empty else pd.DataFrame()
if not today_records.empty:
    if 'show_all' not in st.session_state: st.session_state.show_all=False
    limit = len(today_records) if st.session_state.show_all else 15
    for _,row in today_records.head(limit).iterrows():
        with st.container(border=True):
            ct,ca,cs,cd = st.columns([1,2,1,1])
            ct.write(row['start_time'])
            ca.write(app_name(row['process_name'], row.get('window_title','')))
            cs.write(scene_names.get(row['scene'],row['scene']))
            cd.write(f'{row.get("duration_min",0):.0f}分' if row.get('duration_min',0)>0 else '')
    if len(today_records)>15:
        if st.session_state.show_all:
            if st.button('收起',use_container_width=True): st.session_state.show_all=False;st.rerun()
            st.caption(f'共 {len(today_records)} 条')
        else:
            if st.button(f'展示全部 ({len(today_records)} 条)',use_container_width=True): st.session_state.show_all=True;st.rerun()
    csv=today_records[['start_time','process_name','scene','window_title','duration_min']].to_csv(index=False,encoding='utf-8-sig').encode('utf-8-sig')
    st.download_button('导出CSV',data=csv,file_name=f'behavior_{today_str}.csv',mime='text/csv',use_container_width=True)
else: st.info('今天还没有行为记录')

# ---- 6. 7天趋势 ----
st.subheader('最近7天趋势')
from database.db import get_weekly_summary
wrows=get_weekly_summary()
if wrows:
    wdf=pd.DataFrame([dict(r) for r in wrows])
    wdf['场景名']=wdf['scene'].map(scene_names).fillna(wdf['scene'])
    wdf['小时']=wdf['total_min']/60
    piv=wdf.pivot_table(index='summary_date',columns='场景名',values='小时',aggfunc='sum',fill_value=0)
    if not piv.empty:
        ld=piv.reset_index().melt(id_vars='summary_date',var_name='场景名',value_name='小时')
        ln=alt.Chart(ld).mark_line(point=True).encode(
            x=alt.X('summary_date:T',title='日期',axis=alt.Axis(labelAngle=0)),y='小时:Q',
            color=alt.Color('场景名',scale=alt.Scale(domain=list(scene_colors.keys()),range=list(scene_colors.values())))
        ).properties(height=200)
        st.altair_chart(ln,use_container_width=True)
else: st.info('趋势数据不足')

# ---- 7. 优化建议 ----
st.subheader('优化建议')
if not df_today.empty:
    tips=[]
    for sk,tmpl in [('work','已使用 {n} 次（{h:.0f}分），可考虑自动化'),('study','已学习 {h:.0f} 分，建议做笔记巩固')]:
        sub=df_today[df_today['scene']==sk]
        if len(sub)>=3:
            for _,r in sub.groupby('process_name').agg(n=('id','count'),h=('duration_min','sum')).reset_index().iterrows():
                if r['n']>=3 and r['h']>=20: tips.append({'app':app_name(r['process_name']),'tip':tmpl.format(n=int(r['n']),h=r['h'])})
    lt=df_today[df_today['scene']=='leisure']['duration_min'].sum()
    if lt>=60: tips.append({'app':'娱乐','tip':f'今日娱乐{lt/60:.1f}h，注意平衡'})
    for s in tips[:5]: st.container(border=True).write(f'**{s["app"]}**');st.caption(s['tip'])
    if not tips: st.info('暂无明显需要优化的行为')
else: st.info('今日暂无数据')

# ---- 8. AI 洞察 ----
st.divider();st.subheader('AI 智能洞察')
if not os.getenv('AI_API_KEY'):
    k=st.text_input('API Key',type='password',key='aik')
    u=st.text_input('API 地址',value='https://api.deepseek.com',key='aiu')
    if st.button('保存',key='sav') and k:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'.env'),'w') as f:
            f.write(f'AI_API_KEY=***\nAI_BASE_URL={u}\nAI_MODEL=deepseek-chat\n')
        os.environ['AI_API_KEY']=k;os.environ['AI_BASE_URL']=u;st.rerun()
    st.info('可去阿里云百炼申请免费额度')
else:
    if 'insight_json' not in st.session_state:
        d=build_insight_json()
        if d: st.session_state.insight_json=d
    if 'insight_json' in st.session_state:
        data=st.session_state.insight_json
        ca,cb,cc,cd=st.columns(4)
        with ca:
            if st.button('今日洞察',use_container_width=True,key='bi'):
                with st.spinner('分析中...'): st.session_state.ai_insight=ai_daily_insight(data)
        with cb:
            if st.button('优化建议',use_container_width=True,key='ba'):
                with st.spinner('分析中...'): st.session_state.ai_advice=ai_optimization_advice(data)
        with cc:
            if st.button('趋势分析',use_container_width=True,key='bt'):
                with st.spinner('分析中...'): st.session_state.ai_trend=ai_trend_analysis(data)
        with cd:
            if st.button('用户画像',use_container_width=True,key='bp'):
                with st.spinner('分析中...'): st.session_state.ai_profile=ai_user_profile(data)
        for k,l in [('ai_insight','今日洞察'),('ai_advice','优化建议'),('ai_trend','趋势分析'),('ai_profile','用户画像')]:
            if k in st.session_state:
                with st.container(border=True): st.write(f'**{l}**');st.write(st.session_state[k])
        st.divider();st.subheader('问问 PersonalInsightAI')
        q=st.text_input('',placeholder='例如：今天效率为什么下降？',label_visibility='collapsed',key='aq')
        if st.button('分析',use_container_width=True,key='ask') and q.strip():
            with st.spinner('分析中...'): st.session_state.ai_chat=[{'q':q,'a':ai_ask(q,data)}];st.rerun()
        if 'ai_chat' in st.session_state:
            with st.container(border=True): st.write(f'**你：**{st.session_state.ai_chat[-1]["q"]}');st.write(st.session_state.ai_chat[-1]['a'])

# ---- 底部 ----
st.divider()
thours=df['duration_min'].sum()/60
udays=df['event_date'].nunique()
conn=get_conn()
al=[r[0] for r in conn.execute('SELECT DISTINCT event_date FROM behavior_log ORDER BY event_date').fetchall()]
cd=0;ck=date.today()
for d in reversed(al):
    if date.fromisoformat(d)==ck: cd+=1;ck-=timedelta(days=1)
    else: break
la=get_config('最后分析时间') or '尚未分析'
c1,c2,c3,c4,c5=st.columns(5)
c1.metric('最近分析',la.split()[1] if ' ' in la else la)
c2.metric('覆盖天数',f'{udays} 天')
c3.metric('累计时长',f'{thours:.0f} 小时')
c4.metric('连续采集',f'{cd} 天')
c5.metric('本周数据',f'{len(df)} 条')
st.caption('数据存在本地，不会上传云端')
