"""Video three-track alignment helper."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VideoSegment:
    text: str
    start_ts: float | None
    end_ts: float | None
    visual_evidence: list[str] = field(default_factory=list)
    audio_evidence: list[str] = field(default_factory=list)


def align_video_tracks(
    transcript_rows: list[dict],
    *,
    keyframe_labels: list[str] | None = None,
) -> list[VideoSegment]:
    labels = keyframe_labels or []
    output: list[VideoSegment] = []
    for index, row in enumerate(transcript_rows):
        output.append(
            VideoSegment(
                text=str(row.get("text") or "").strip(),
                start_ts=row.get("start_ts", row.get("start")),
                end_ts=row.get("end_ts", row.get("end")),
                visual_evidence=labels[:1] if index == 0 else [],
                audio_evidence=[row.get("speaker")] if row.get("speaker") else [],
            )
        )
    return [segment for segment in output if segment.text or segment.visual_evidence]
