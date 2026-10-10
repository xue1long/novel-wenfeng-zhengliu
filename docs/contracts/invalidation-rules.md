# 哈希失效规则（Stage A 锁定）

本表把 spec §4.6 的"输入哈希传播失效"翻译为代码可校验的版本，与
`scripts/invalidation_rules.py` 同源。

## 触发与失效范围

| 失效触发 | 失效下游范围 | 备注 |
|---|---|---|
| `source_fingerprint` 变化 | sampling, holdout, extraction, bundle, compilation, evaluation, release | 来源指纹变了，下游全失效 |
| `normalizer_version` 变化 | 同上 | 规范化器版本 |
| `chunker_version` 变化 | 同上 | 分块器版本 |
| `extraction_prompt_version` 变化 | extraction, bundle, compilation, evaluation, release | 提取提示变了 |
| `review_model_id` 变化 | extraction, bundle, compilation, evaluation, release | 复核模型变了 |
| `candidate_schema_version` 变化 | 同上 | 候选 schema 变了 |
| `bundle_version` 变化 | compilation, evaluation, release | Bundle 重出 |
| `template_version` 变化 | 同上 | 六阶段模板变了 |
| `compiler_version` 变化 | 同上 | 编译器变了 |
| `scoring_model_id` 变化 | evaluation, release | 评分模型变了 |
| `scoring_rubric_version` 变化 | 同上 | 量表版本变了 |
| `scan_model_id` 变化 | scan, release | 扫描模型变了 |
| `scan_policy_version` 变化 | scan, release | 扫描策略变了 |
| 单纯 `increase_scan_budget` | 无 | 仅续跑未完成窗口；已完成且输入/提示/模型哈希一致者保留（spec §4.6 显式豁免） |

## 调用方式

```python
from invalidation_rules import InvalidationClass, compute_invalidation

result = compute_invalidation(
    existing_hashes={"scan_windows": {...}},
    changed_classes=[InvalidationClass.SOURCE_FINGERPRINT],
    increased_scan_budget=False,
)
# result["invalidated"]            -> 受影响的下游类别
# result["completed_windows_preserved"] -> 预算增加时保留下来的扫描窗口
# result["windows_needing_resume"] -> 需要续跑的扫描窗口
```

## 重新锁定留出集

任何 `InValidationClass` 命中 sampling / holdout 链路后，必须按 spec §4.2
重新锁定留出集再继续；之前用过的留出集不能作为独立验收集。

## 测试

- `tests/test_invalidation.py` 覆盖每一类触发与"仅增加扫描预算"豁免的反向用例。
- 修改本表必须同步修改 `scripts/invalidation_rules.py` 并跑上述测试。