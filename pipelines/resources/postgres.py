"""PostgreSQL resource metadata for Week06 Dagster definitions."""

from dagster import ConfigurableResource


class PostgresResource(ConfigurableResource):
    database_url: str

    @property
    def masked_url(self) -> str:
        if "@" not in self.database_url or "://" not in self.database_url:
            return self.database_url
        scheme, rest = self.database_url.split("://", 1)
        _, host = rest.rsplit("@", 1)
        return f"{scheme}://***:***@{host}"
