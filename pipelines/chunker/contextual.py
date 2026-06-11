"""Contextual retrieval helpers for Week07 chunks."""


def build_context_prefix(
    *,
    doc_title: str | None = None,
    section_path: str | None = None,
    heading_path: list[str] | None = None,
    max_chars: int = 240,
) -> str:
    parts: list[str] = []
    if doc_title:
        parts.append(f"Document: {doc_title}")
    if heading_path:
        parts.append("Path: " + " > ".join(heading_path))
    elif section_path:
        parts.append(f"Section: {section_path}")

    prefix = " | ".join(parts)
    return prefix[:max_chars]


def apply_contextual_prefix(content: str, context_prefix: str | None) -> str:
    if not context_prefix:
        return content
    return f"{context_prefix}\n\n{content}"
