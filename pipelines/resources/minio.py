"""MinIO resource metadata for Week06 Dagster definitions."""

from dagster import ConfigurableResource


class MinIOResource(ConfigurableResource):
    endpoint: str
    access_key: str
    secret_key: str

    @property
    def masked_endpoint(self) -> str:
        return self.endpoint
