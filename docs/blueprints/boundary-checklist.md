# OmniSupport Copilot — 业务验收口径 & 风险边界清单 v1.0

> 文档定位：风险边界前置声明 | 贯穿 Week01–Week15
> 最后更新：2026-03-31

---

## 1. 系统边界（做什么 / 不做什么）

### ✅ 系统做

| 类别 | 具体能力 |
|------|---------|
| 知识问答 | 回答产品使用、配置、故障排查问题，带证据引用 |
| 工单操作 | 查询工单状态、创建新工单、更新工单（受权限约束） |
| 指标查询 | 查询 SLA 合规率、工单统计等支持 KPI |
| 多模态检索 | 检索 PDF、HTML、FAQ、音频转写、视频片段 |
| 人工介入 | P1/P2 工单、安全类问题自动触发 HITL |
| 审计追踪 | 所有高风险动作记录 `request_id`、`actor`、`tool_name`、`result_code` |
| 版本与回滚 | 支持按 release_id 回滚数据/索引/prompt 组合 |

### ❌ 系统不做

| 类别 | 说明 |
|------|------|
| 开放域聊天 | 不回答与 Northstar Systems 产品无关的问题 |
| 无限制自动执行 | 任何影响外部状态的操作必须受权限和 HITL 约束 |
| 自动学习 / RLHF | 课程范围内不做在线学习或模型微调 |
| 实时通话接听 | 音频仅做离线转写处理，不做实时语音交互 |
| 跨租户数据访问 | 严格隔离不同 org_id 的数据访问权限 |

---

## 2. 数据边界

### 2.1 PII 处理规则

| 数据类型 | PII 级别 | 处理要求 |
|---------|---------|---------|
| 工单描述 | 可能 high | 入库前扫描，`pii_redacted=true` 后才能进入检索索引 |
| 音频转写 | high | 必须脱敏后才能存入 Silver 层 |
| 客户 email/电话 | high | 不入检索索引，仅存结构化 `customer_dim` |
| 文档内容 | 通常 none/low | 公开文档无需脱敏 |

### 2.2 版权与分发规则

| 数据来源 | 许可策略 | 分发方式 |
|---------|---------|---------|
| 公共种子（MS Learn 等） | 按原始 license | 仅作为构建原料，不直接分发原始抓取结果 |
| 课程规范化资产 | course_synthetic | 直接分发给学员 |
| 合成工单/音频 | course_synthetic | 直接分发给学员 |
| 真实客服音频 | proprietary | 不分发，仅用转写文本 |

### 2.3 数据包规模边界

| 数据包 | 规模 | 用途 |
|--------|------|------|
| Student Core Pack | 1,200–1,800 源资产；6–12 万 chunk | 学员本地开发，Docker Compose 单机可跑 |
| Instructor Scale Pack | 6,000–10,000 源资产；20–50 万 chunk | 讲师演示规模差异，需共享实验环境 |

---

## 3. 工具调用边界

### 3.1 权限矩阵

| 工具 | end_user | support_agent | admin |
|------|---------|--------------|-------|
| search_knowledge | ✅ | ✅ | ✅ |
| get_ticket_status | ✅（仅自己的） | ✅ | ✅ |
| create_ticket | ✅ | ✅ | ✅ |
| update_ticket | ❌（需 agent） | ✅ | ✅ |
| query_kpi | ❌ | ✅ | ✅ |
| escalate_to_human | ✅ | ✅ | ✅ |
| get_allowed_actions | ✅ | ✅ | ✅ |

### 3.2 必须触发 HITL 的场景

- 工单优先级为 `p1_critical`
- 工单类别为 `security` 且优先级 >= `p2_high`
- 检索置信度 < 0.4 且涉及安全/权限相关问题
- 任何涉及账单变更、权限变更的操作

### 3.3 幂等性要求

- 所有"写"操作（create_ticket, update_ticket）必须支持 `idempotency_key`
- 同一 idempotency_key 在 24 小时内重复调用返回原结果，不创建新记录

---

## 4. 工程质量门禁

### 4.1 最低可接受线（Week01）

- [ ] `docker compose up` 无错退出，9 个服务健康
- [ ] contracts/ 下所有 JSON Schema 通过 `jsonschema` lint
- [ ] README 能解释业务世界观与启动方式
- [ ] 存在至少 1 份 data contract 样板、1 份 tool contract 样板、1 份 release manifest 样板

### 4.2 Week08 前必须满足（RAG 上线门禁）

- [ ] 所有 RAG 响应包含 `citations`, `evidence_ids`, `trace_id`, `release_id`
- [ ] 检索 p@5 >= 0.6（最小 eval 集）
- [ ] 100% API 请求有 OTel trace
- [ ] 至少 1 条 bad case 可通过 trace 定位

### 4.3 Week14 前必须满足（治理门禁）

- [ ] lakeFS 已接入，data branch/merge 可演示
- [ ] OpenLineage 血缘已接入，dataset → job → run 可追踪
- [ ] Release Manifest 已绑定 data/index/prompt/eval 四个版本

---

## 5. 已知风险与缓解策略

| 风险 | 影响 | 缓解策略 |
|------|------|---------|
| 客服音频公开可用性极差 | 音频层内容稀少 | 采用 TTS + 噪声合成 + 公开转写集双轨策略 |
| 视频原始内容版权复杂 | 分发受限 | 优先分发转写文本 + 关键帧 OCR，不分发原始视频 |
| Student Core Pack 规模过大无法本地跑 | 学员体验差 | 严格控制 chunk 数量在 12 万以内；优先保证稳定 |
| 模型生成内容无证据支撑 | 幻觉风险 | Evidence-first 原则，无高分检索结果时拒绝生成 |
| 工具调用越权 | 安全风险 | 所有工具调用前检查 allowed_roles，HITL 前置 |
| 版本漂移（数据/索引/prompt 不同步） | 评测不可重复 | Release Manifest 强制绑定四个版本 ID |

---

## 6. 非功能性最低标准

| 维度 | 最低标准 |
|------|---------|
| 可重复 | 同 data_release_id + index_release_id + prompt_release_id 离线评测可复现 |
| 可观测 | 所有对外请求携带 trace_id；检索/重排/生成/工具调用有关键 span |
| 可回滚 | 发现问题后可在 30 分钟内回滚到上一稳定 release |
| 可审计 | 高风险操作记录 request_id, actor, tool_name, args_hash, result_code |
| 可切换 | Student Core Pack 与 Instructor Scale Pack 共用同一接口与契约，不允许写两套代码 |
