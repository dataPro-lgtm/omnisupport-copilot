"""OTel + OpenInference 可观测性初始化

Week01 提供骨架，Week12 完整接入 Phoenix 与 bad case replay。
"""

import logging

logger = logging.getLogger(__name__)


def setup_telemetry(service_name: str = "rag_api") -> None:
    """初始化 OpenTelemetry tracing。

    设计选择：
    - 使用 OTLP HTTP exporter，兼容 Phoenix 和其他 OTel 后端
    - OpenInference instrumentation 覆盖 Anthropic 调用
    - 所有 span 自动注入 release_id 作为资源属性
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        from app.config import settings

        if not settings.otel_enabled:
            logger.info("OTel disabled via config")
            return

        resource = Resource.create({
            "service.name": service_name,
            "service.version": "0.1.0",
            "deployment.environment": "dev",
            "omni.release_id": settings.release_id,
        })

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(
            endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces"
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor().instrument()

        logger.info(f"OTel tracing initialized for {service_name}")

    except ImportError as e:
        logger.warning(f"OTel setup skipped (missing dependency): {e}")
    except Exception as e:
        logger.error(f"OTel setup failed: {e}")
