# Canonization — 课程规范化资产

本目录存放将公共种子数据规范化为 **Northstar Systems 统一业务世界观** 的中间产物和最终课程资产。

## 规范化原则

1. 所有产品名、版本号、模块名、错误码统一映射到 Northstar Systems 体系
2. 工单 schema 统一为 `ticket_contract.json`
3. 用户/组织/订阅/SLA 模型统一
4. 知识文档元数据模型统一（含 `source_fingerprint`、`doc_version`、`section_path`）
5. 音视频切片、转写、截图、时间戳元数据统一
6. 引用与审计字段统一（`evidence_anchor`、`trace_id`、`release_id`）

## 目录结构

```
canonization/
├── tickets/        # 规范化工单数据
├── documents/      # 规范化文档资产
├── audio/          # 规范化音频转写
└── video/          # 规范化视频片段元数据
```

## 状态追踪

规范化状态在各 manifest 的 `canonization_status` 字段中追踪：
- `raw`: 原始数据，未处理
- `in_progress`: 正在规范化
- `canonized`: 已完成规范化，可用于课程分发
- `rejected`: 不符合课程标准，不使用
