"""Code-aware chunking adapter.

Tree-sitter is the production direction in the Week07 deck. The classroom path
keeps this dependency optional and falls back to regex-level symbol splitting.
"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class CodeBlock:
    symbol_name: str
    language: str
    span_start: int
    span_end: int
    content: str
    parser_backend: str


SYMBOL_RE = re.compile(r"^(def|class|function|export function|const)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)


def split_code_symbols(source: str, *, language: str = "python") -> list[CodeBlock]:
    matches = list(SYMBOL_RE.finditer(source))
    if not matches:
        return [
            CodeBlock(
                symbol_name="module",
                language=language,
                span_start=0,
                span_end=len(source),
                content=source,
                parser_backend="regex_fallback",
            )
        ]

    blocks: list[CodeBlock] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        blocks.append(
            CodeBlock(
                symbol_name=match.group(2),
                language=language,
                span_start=start,
                span_end=end,
                content=source[start:end].strip(),
                parser_backend="regex_fallback",
            )
        )
    return blocks
