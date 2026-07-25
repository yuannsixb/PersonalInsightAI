# PersonalInsightAI

基于用户行为日志的数据分析平台。

自动采集电脑使用行为，完成数据清洗、场景分类、统计分析，并生成可视化洞察报告。

## 数据流程

```
用户行为
    ↓
Agent 采集（10s/次）
    ↓
SQLite 存储
    ↓
场景分类（关键词匹配）
    ↓
Pandas 聚合统计
    ↓
Dashboard 展示
    ↓
洞察报告
```

## 功能

- **行为采集**：每 10 秒记录一次当前活跃窗口（进程名 + 窗口标题）
- **场景分类**：基于关键词将窗口标题映射为 work / study / leisure / life / unknown
- **行为合并**：连续相同场景自动合并为行为段
- **统计分析**：按场景聚合，统计时长、频率、占比
- **数据 Dashboard**：Streamlit 可视化，展示时间分布、场景来源、趋势图
- **自动报告**：每 6 小时生成洞察报告

## 技术栈

| 模块 | 技术 |
|------|------|
| 数据采集 | Python + ctypes (Win32 API) |
| 数据存储 | SQLite |
| 数据分析 | Pandas (groupby / agg / sort) |
| 可视化 | Streamlit + Altair |
| 分类引擎 | CSV 关键词映射表（338 条） |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动采集器
python -m agent.agent start

# 3. 查看状态
python -m agent.agent status

# 4. 打开 Dashboard
streamlit run app.py
```

## 项目结构

```
PersonalInsightAI/
│
├── app.py                 # Dashboard 入口
├── config.py              # 全局配置
├── requirements.txt
├── README.md
├── .gitignore
│
├── agent/
│   ├── agent.py           # 采集主程序
│   └── window.py          # 窗口信息获取
│
├── analysis/
│   ├── reporter.py        # 洞察报告生成
│   ├── scene_classifier.py# 场景分类引擎
│   ├── data_cleaning.py
│   ├── feature_engineering.py
│   ├── user_profile.py
│   ├── recommendation.py
│   ├── anomaly_detection.py
│   ├── ai_explain.py
│   └── notifier.py
│
├── database/
│   └── db.py              # SQLite 操作
│
├── data/
│   └── scene_dictionary.csv  # 场景关键词映射表
│
└── docs/
    └── data_flow_diagram.svg
```
