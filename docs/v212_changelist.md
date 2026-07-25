# PersonalInsightAI v2.1.2 修改说明

---

## 改了 7 个地方

| # | 问题 | 类型 | 改动 |
|---|------|------|------|
| ① | 采集间隔 30s 丢数据 | **必须改** | → **10s** |
| ② | 窗口标题截断 80 字符 | **必须改** | → **不截断**，SQLite 无压力 |
| ③ | Reporter 全表扫 | **必须改** | → `WHERE event_date >= 7天前` |
| ④ | 浏览器关键词误判 | **必须改** | → `classify_browser()` 独立处理 |
| ⑤ | json 知识库不好维护 | **建议改** | → **CSV 格式**，Excel 就能改 |
| ⑥ | 缺少 Top 5 应用 | **建议改** | → Dashboard 新增"今日 Top 5" |
| ⑦ | 缺少数据质量卡片 | **建议改** | → 显示 总条数/已识别/待分类/识别率 |

---

## 详细改动

### ① 采集间隔 10 秒
**文件：** `agent.py`
```python
COLLECT_INTERVAL = 10  # 之前是 30
```
10 秒保证短操作（切窗口、看消息）不被漏掉。CPU 几乎无差别。

### ② 窗口标题不截断
**文件：** `agent.py`
```python
window_title[:80]  →  window_title  # 不截断
```
之前截 80 字可能把后面关键信息切掉。SQLite 存几千字符毫无压力。

### ③ Reporter 加 WHERE 过滤
**文件：** `analysis/reporter.py`
```sql
-- 之前
SELECT * FROM behavior_log

-- 现在
SELECT event_date, start_time, duration_min, process_name, scene, window_title
FROM behavior_log WHERE event_date >= ?
```
参数传 `7 天前` 日期。性能提升，企业标准写法。

### ④ 浏览器独立分类
**文件：** `agent.py` + `analysis/scene_classifier.py`

之前：进程名→场景→如果是 browser→再猜一次。
现在：**浏览器直接走 `classify_browser()`**，不看进程名。

逻辑：
```
浏览器窗口（Edge/Chrome）
  ↓
只看窗口标题
  ↓
完全由关键词决定分类
  ↓
避免 "Excel" 在看视频时被误判为工作
```

普通程序（BF2042, Code.exe, Weixin 等）继续走 `classify()`，通过进程名兜底。

### ⑤ 知识库改成 CSV
**文件：** `scene_dictionary.json` → `scene_dictionary.csv`

| keyword | scene |
|---------|-------|
| ChatGPT | study |
| GitHub | work |
| 抖音 | leisure |
| ... | ... |

共 **338 条关键词**，5 个场景。

**好处：** 用户用 Excel 打开、修改、保存，项目直接重新加载生效。不再需要编辑 JSON。

### ⑥ 今日 Top 5
**文件：** `streamlit_app.py`

Dashboard 新增"今日 Top 5"模块，展示：
```
今日 Top 5
ChatGPT      65分钟  study
GitHub       40分钟  work
Battlefield  30分钟  leisure
...
```
代码：一行 `df.groupby('process_name').sum().sort_values().head(5)`

### ⑦ 数据质量卡
**文件：** `streamlit_app.py`

在今日状态下方新增：
```
📊 今日数据质量: 186 条 | 已识别 175 条 | 待分类 11 条 | 识别率 94%
```

---

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `agent.py` | 10s 采集 + 标题不截断 + 浏览器独立分类 |
| `analysis/scene_classifier.py` | CSV 加载 + 浏览器独立接口 |
| `analysis/reporter.py` | WHERE 过滤 + 今日速览 |
| `streamlit_app.py` | WHERE 过滤 + Top 5 + 数据质量卡 |
| `scene_dictionary.csv` | 新增（替代 json） |
| `scene_dictionary.json` | 保留作为备份 |

---

## 测试结果（全部通过）

```
浏览器分类:
  ChatGPT           → study   ✅
  Excel教程-B站      → work    ✅（关键词自然匹配）
  抖音              → leisure ✅
  牛客              → study   ✅
  GitHub            → work    ✅
  淘宝              → life    ✅
  12306             → life    ✅

普通程序:
  BF2042            → leisure ✅
  Code + agent.py   → work    ✅
  微信              → leisure ✅
  notepad           → unknown ✅

数据库: INSERT ✓, GROUP BY scene ✓
词库: 338 条 CSV 关键词, 加载成功 ✓
```

---

## 下一版方向（ChatGPT 建议）

不要继续改底层了。下一版围绕**数据分析指标**：
- 今日效率指数
- 最近 7 天趋势
- Top 5 应用
- 待分类率
- 学习/娱乐占比
- 连续学习天数（Streak）
