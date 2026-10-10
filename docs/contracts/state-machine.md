# Run 状态机（Stage A 锁定）

本表把 spec §4.6 的状态集合与合法 / 硬阻断转移翻译为代码可校验的版本，与
`scripts/state_machine.py` 同源。修改任一处都必须同步另一处并跑
`tests/test_state_machine.py`。

## 状态集合

`incomplete` · `blocked` · `limited` · `ready`

## 转移表

| 起始状态 | 事件 | 目标状态 | 备注 |
|---|---|---|---|
| incomplete | `step_resumed` | incomplete | 幂等续跑 |
| incomplete | `step_failed` | incomplete | 等待重试 / 续跑 |
| incomplete | `authorization_missing` | blocked | 授权缺失或越范围（spec §4.6） |
| incomplete | `scan_budget_exhausted` | incomplete | 续跑窗口，等待预算续期 |
| incomplete | `evidence_quote_invalid` | blocked | 偏移/哈希校验失败 |
| incomplete | `exact_copy_detected` | blocked | 编译预检命中长段复制 |
| incomplete | `semantic_risk_flagged` | blocked | 语义扫描判为 risk |
| incomplete | `schema_validation_failed` | blocked | 任一 schema 校验失败 |
| limited | `all_gates_passed` | ready | 仅当授权允许分享时真为 ready |
| limited | `scan_budget_exhausted` | limited | 留待续跑 |
| limited | `semantic_risk_flagged` | blocked | 不允许已收录结果带风险发布 |
| limited | `evidence_quote_invalid` | blocked | 已通过的 evidence 被推翻即降级为 blocked |
| ready | `release_artifact_built` | ready | 终态 |
| ready | `post_release_drift_detected` | blocked | 发布后任何漂移即硬阻断 |
| blocked | `step_resumed` | blocked | blocked 不能自愈为 ready；只能继续调查 |

## 终态计算

`scripts/state_machine.compute_final_state(gates_passed, authorization_purpose)`
根据 gates 集合与授权范围返回 `incomplete / blocked / limited / ready`。门
集合至少应包含 `bundle_valid / extraction_valid / eval_passed / scan_complete`
四项；任一缺位即降为 `limited`（除非授权禁止分享）。`exact_copy_detected`
/`semantic_risk_flagged`/`authorization_missing` 三个硬门任一未通过 → `blocked`。

## 阻止发布的硬门

- `blocked`：任何硬阻断命中（授权、证据、复制、语义扫描）。禁止编译或分享。
- `limited`：覆盖/结论不确定或效果评测未达门槛。只允许私有预览，不允许
  `shareable` 发布。
- `ready`：所有门通过；只有授权允许分享时才生成 shareable ZIP。

## 与 Bundle / Stage-context 的耦合

- Bundle 的 `evidence_status` 仅描述机制证据；本表描述**整条 pipeline**。
  两者必须一致：机制 evidence_status=approved 也不能让 blocked 的 pipeline
  发布。
- stage-context 的 `return_to` 不得跨越本表的硬阻断边；回退到上游阶段后只重跑
  受影响的下游，不绕开本表。