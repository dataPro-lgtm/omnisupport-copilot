# Asset Flow Plan v1

## 目标

明确当前 repo 中不同输入资产从 manifest 到下游落点的最小流向。

## Document Flow

1. `manifest_workspace_helpcenter_v1.json` / `manifest_edge_gateway_pdf_v1.json`
2. `seed_loader.py` admission
3. `doc_ingest.py`
4. `raw_doc_asset`
5. `knowledge_doc`
6. `doc_parser.py`
7. `knowledge_section`
8. `evidence_anchor`
9. `embedder.py`
10. `rag_api retrieval`

## Ticket Flow

1. `manifest_tickets_synthetic_v1.json`
2. `seed_loader.py` admission
3. `ticket_simulator.py` 生成 JSONL
4. `ticket_ingest.py`
5. `raw_ticket_event`
6. `ticket_fact`

## Audio / Video Flow

当前状态：

- contract 已有
- inventory / metadata / PII policy 已有
- manifest schema 已支持
- 但真实 ingest 执行器还未落地

因此：
- Week03 只把它们保持在“受控制、未 fully onboarded”的状态
- 不强推到真实执行

## Week03 之后的继续方向

- Week04：把 batch / state / replay 语义带入更正式的数据版本控制
- Week06：把 recovery decision 接入 orchestrator
