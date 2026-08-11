from poker.statistics.database.sqlalchemy_real import (
	AgentMemoryORM,
	Base,
	PlayerORM,
)


def test_real_orm_models_exist():
	assert Base
	assert PlayerORM.__tablename__ == "players"
	assert AgentMemoryORM.__tablename__ == "agent_memory"
