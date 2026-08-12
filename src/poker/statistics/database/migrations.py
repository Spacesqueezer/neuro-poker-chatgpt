from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config


@dataclass(frozen=True)
class MigrationConfig:
	database_url: str
	alembic_ini: str = "alembic.ini"


def _build_alembic_config(config: MigrationConfig) -> Config:
	alembic_config = Config(str(Path(config.alembic_ini)))
	alembic_config.attributes["database_url"] = config.database_url
	return alembic_config


def upgrade_database(
	config: MigrationConfig,
	revision: str = "head",
) -> None:
	command.upgrade(
		_build_alembic_config(config),
		revision,
	)


def downgrade_database(
	config: MigrationConfig,
	revision: str = "base",
) -> None:
	command.downgrade(
		_build_alembic_config(config),
		revision,
	)
