from typing import List, Optional

from retriever.lib.models import Evidence, RetrievalResult


def _normalize_content(content: str) -> str:
    """将内容压缩为空格，便于去重时对齐。"""
    return " ".join((content or "").split())


def dedupe_by_display_keep_longest(evidences: List[Evidence]) -> List[Evidence]:
    """
    基于正文内容去重：同一 doc 内正文相同只保留路径最长的证据
    """
    if not evidences:
        return evidences
    best_by_content = {}
    for ev in evidences:
        # 去重时不使用行号等展示信息，使用归一化正文 + doc_id 作为键
        content_key = f"{ev.doc_id}||{_normalize_content(ev.content)}"
        existing = best_by_content.get(content_key)
        if existing is None or len(ev.file_path or "") > len(existing.file_path or ""):
            best_by_content[content_key] = ev
    return list(best_by_content.values())


def dedupe_merge_by_path_lines(evidences: List[Evidence], stage: str, logger) -> List[Evidence]:
    """
    路径/行号合并：
    - 展示内容去重（保留路径最长）
    - 同一路径且行号重叠则合并内容，扩展行号
    """
    if not evidences:
        return evidences
    before = len(evidences)
    deduped = dedupe_by_display_keep_longest(evidences)

    merged: List[Evidence] = []
    by_path = {}
    for ev in deduped:
        path = ev.file_path or ""
        by_path.setdefault(path, []).append(ev)

    for _, evs in by_path.items():
        if len(evs) == 1:
            merged.append(evs[0])
            continue

        evs_sorted = sorted(evs, key=lambda x: (x.start_line or 0, x.end_line or 0))
        current = evs_sorted[0]
        for nxt in evs_sorted[1:]:
            if (
                current.start_line is not None
                and current.end_line is not None
                and nxt.start_line is not None
                and nxt.end_line is not None
                and nxt.start_line <= current.end_line
            ):
                # 行号重叠，按行号融合内容，避免重复行
                lines_cur = current.content.splitlines()
                lines_nxt = nxt.content.splitlines()
                tail_start = max(0, current.end_line - nxt.start_line + 1)
                tail_lines = lines_nxt[tail_start:] if tail_start < len(lines_nxt) else []
                merged_lines = lines_cur + tail_lines
                current.content = "\n".join(merged_lines)
                current.end_line = max(current.end_line, nxt.end_line)
                current.relevance_score = max(current.relevance_score, nxt.relevance_score)
                current.retrieval_score = max(current.retrieval_score, nxt.retrieval_score)
            else:
                merged.append(current)
                current = nxt
        merged.append(current)

    after = len(merged)
    if after < before:
        logger.info(f"{stage} 路径/行号合并: {before} -> {after} 个证据")
    return merged


def filter_deep_zero_txt(evidences: List[Evidence], stage: str, logger) -> List[Evidence]:
    """
    过滤深层 0.txt：仅当路径中 _split 次数>=2 且文件名为 0.txt 时过滤
    """
    if not evidences:
        return evidences
    filtered = []
    removed = 0
    for ev in evidences:
        path = ev.file_path or ""
        if path.endswith("0.txt") and path.count("_split") >= 2:
            removed += 1
            continue
        filtered.append(ev)
    if removed:
        logger.info(f"{stage} 过滤深层0.txt: {len(evidences)} -> {len(filtered)} 个证据")
    return filtered


def verify_and_merge(
    *,
    stage: str,
    query: str,
    verification_query: Optional[str] = None,
    new_evidences: List[Evidence],
    result: RetrievalResult,
    verifier,
    config: dict,
    logger,
    keywords: Optional[List[str]] = None,
    reasoning: Optional[str] = None,
    filter_zero: bool = True,
) -> float:
    """
    通用验证合并流程：
    - 可选过滤深层 0.txt
    - 路径/行号合并
    - 验证打分并按阈值过滤
    - 合并到结果并排序
    返回本轮最高验证分数
    """
    if not new_evidences:
        return 0.0

    if filter_zero:
        new_evidences = filter_deep_zero_txt(new_evidences, stage, logger)
    new_evidences = dedupe_merge_by_path_lines(new_evidences, stage, logger)

    if not new_evidences:
        return 0.0

    for ev in new_evidences:
        ev.retrieval_score = ev.relevance_score

    verification_scores = verifier.verify(verification_query or query, new_evidences)
    quality_config = config.get("quality", {})
    min_score_threshold = quality_config.get("min_score_threshold", 0.5)
    # 使用与min_score_threshold相同的默认值，确保阈值一致性
    verification_score_threshold = quality_config.get("verification_score_threshold", min_score_threshold)

    filtered_new_evidences = []
    offset = len(result.verification_scores)
    new_index = 0
    for i, ev in enumerate(new_evidences):
        idx_str = str(i)
        if idx_str in verification_scores:
            ver_score = verification_scores[idx_str]
            if ver_score > verification_score_threshold:
                ev.relevance_score = ver_score
                filtered_new_evidences.append(ev)
                result.verification_scores[str(offset + new_index)] = ver_score
                new_index += 1

    if len(new_evidences) > len(filtered_new_evidences):
        filtered_count = len(new_evidences) - len(filtered_new_evidences)
        logger.info(f"{stage} 过滤验证分数低于或等于阈值的证据: {filtered_count} 个（阈值: {verification_score_threshold:.2f}）")

    if not filtered_new_evidences:
        return 0.0

    result.evidences.extend(filtered_new_evidences)
    result.evidences.sort(key=lambda x: x.relevance_score, reverse=True)
    result.total_results = len(result.evidences)

    if keywords is not None:
        result.keywords = keywords
    if reasoning is not None:
        result.reasoning = reasoning

    return max(ev.relevance_score for ev in filtered_new_evidences)

