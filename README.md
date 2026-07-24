# PersonalInsightAI

基于用户行为日志的个人效率分析平台。

自动采集电脑使用行为，通过场景分类 + 用户自定义知识库实现智能分析，生成可视化洞察报告和优化建议。

## 数据流程

```
用户行为
    ↓
Agent 采集（10s/次，窗口切换判断）
    ↓
缓冲批量写入（攒 10 条写一次） → SQLite（按日期/场景/进程建索引）
    ↓
场景分类（用户知识库 > 标题关键词 > 进程名兜底）
    ↓
Pandas 聚合统计
    ↓
Dashboard 展示 + 知识库反馈闭环
    ↓
AI 智能洞察
```

## 功能

### 采集
- 每 10 秒检测活跃窗口，窗口切换才落库（避免无效数据）
- 批量写入 + WAL 模式，减少 IO
- 支持暂停/恢复

### 分类
- **场景字典**：338 条关键词，覆盖工作/学习/娱乐/生活
- **用户知识库**：自定义分类规则，最高优先级
- **分类缓存**：相同进程+标题短时间不重复判断
- **别名匹配**：输入"微信"自动匹配 `Weixin.exe`

### Dashboard（Streamlit）
- 今日状态总览（效率指数 / 各场景时长）
- 时间分布柱状图
- 各场景来源明细
- 7 天趋势折线图
- 行为记录 + 导出 CSV
- 优化建议
- **我的知识库**：增删改查自定义规则
- AI 智能洞察（可选，需 API Key）

### 性能优化
- SQLite 索引（event_date / scene / process_name / created_at）
- 批量写入（10 条一提交）
- 连接复用（单例连接，死连自动重建）
- 内存缓存（用户规则一次加载，后续 O(1) 查询）
- 历史数据自动清理（默认保留 90 天）

## 技术栈

| 模块 | 技术 |
|------|------|
| 数据采集 | Python + ctypes (Win32 API) |
| 数据存储 | SQLite（索引 + WAL + 批量写入） |
| 数据分析 | Pandas (groupby / agg / 特征工程) |
| 可视化 | Streamlit + Altair |
| 分类引擎 | CSV 关键词映射表 + 用户自定义规则 |
| AI | 兼容 OpenAI / DeepSeek API |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动采集器
python agent.py detach

# 3. 查看状态
python agent.py status

# 4. 打开 Dashboard
streamlit run app.py
```

## 项目结构

```
PersonalInsightAI/
│
├── app.py                    # Dashboard 入口
├── agent.py                  # 采集器入口
├── config.py                 # 全局配置
├── scene_dictionary.csv      # 场景关键词映射表（338 条）
├── requirements.txt
│
├── agent/
│   ├── agent.py              # 采集主程序（窗口切换判断 + 批量写入）
│   └── window.py             # Windows 窗口信息获取
│
├── analysis/
│   ├── scene_classifier.py   # 场景分类引擎（内存缓存 + 用户规则优先）
│   ├── user_dictionary.py    # 用户知识库管理（缓存刷新）
│   ├── reporter.py           # 洞察报告生成
│   ├── ai_explain.py         # AI 分析接口
│   ├── data_cleaning.py
│   ├── feature_engineering.py
│   ├── user_profile.py
│   └── anomaly_detection.py
│
├── database/
│   └── db.py                 # SQLite 操作（索引 + 批量缓冲 + 连接复用 + 别名匹配）
│
└── docs/
    └── data_flow_diagram.svg
```
