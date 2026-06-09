"""Audio transcript processing.

Whisper/pyannote are production adapters. The default classroom path consumes
versioned transcript sidecars so the parse pipeline remains reproducible.
"""

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class AudioSegment:
    text: str
    speaker: str | None
    start_ts: float | None
    end_ts: float | None


def segments_from_transcript_sidecar(transcript_text: str) -> list[AudioSegment]:
    segments: list[AudioSegment] = []
    for line in transcript_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            segments.append(
                AudioSegment(
                    text=str(payload.get("text") or payload.get("content") or "").strip(),
                    speaker=payload.get("speaker") or payload.get("speaker_role"),
                    start_ts=payload.get("start_ts", payload.get("start")),
                    end_ts=payload.get("end_ts", payload.get("end")),
                )
            )
        except json.JSONDecodeError:
            segments.append(AudioSegment(text=line, speaker=None, start_ts=None, end_ts=None))
    return [segment for segment in segments if segment.text]
