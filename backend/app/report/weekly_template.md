# {{ title }}

> 期号 #{{ issue_no }} · {{ period_start }} ~ {{ period_end }}
> 自动扫描 {{ source_count }} 个公开数据源 · 共采集 {{ raw_count }} 条原始信号 · 聚类出 {{ cluster_count }} 个主题

---

## 本期速览

- **Top {{ items|length }} 痛点榜**：覆盖 {{ unique_clusters }} 个独立主题
- **新晋 go**：{{ new_go_count }} 条
- **平均总分**：{{ avg_score }}
- **强付费意愿信号**：{{ strong_wtp_count }} 条
{% if highlight %}
- **本期重点**：{{ highlight }}
{% endif %}

---

{% for item in items %}
## #{{ loop.index }} · {{ item.pain }}

`总分 {{ item.total_score }}` · `{{ item.go_no_go }}` · `{{ item.willingness_to_pay_signal }}付费意愿` · `频次 {{ item.frequency_signal }}`

{% if item.scenario %}**场景**：{{ item.scenario }}{% endif %}
{% if item.target_user %}**目标用户**：{{ item.target_user }}{% endif %}

{% if item.evidence %}
**证据**：
{% for e in item.evidence %}
- [{{ e.source }}] {{ e.title or (e.text or '')[:60] }} {% if e.url %}— [原文]({{ e.url }}){% endif %}
{% endfor %}
{% endif %}

{% if item.rationale %}
> {{ item.rationale }}
{% endif %}

{% if not loop.last %}---{% endif %}
{% endfor %}

---

## 数据源覆盖（本期）

{% for src, n in source_breakdown %}
- `{{ src }}`：{{ n }} 条
{% endfor %}

---

*本周报由 DemandRadar 自动生成。订阅完整周报：[demandradar.com](https://demandradar.com)*
*合规说明：仅采集公开数据；引用 ≤30 字并附原文链接。Takedown: takedown@example.com*
