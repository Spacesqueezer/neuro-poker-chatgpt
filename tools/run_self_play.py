import argparse
import json
import os
from pathlib import Path

from poker.agents.neural import NeuralAgent
from poker.arena.runner import ArenaRunner
from poker.learning.dataset import LearningDatasetWriter
from poker.learning.rl_dataset import RLDatasetCapture
from poker.learning.self_play import ModelPool

def setup_statistics():
	from sqlalchemy import create_engine
	from sqlalchemy.orm import sessionmaker
	from poker.statistics.database.sqlalchemy_models import DeclarativeBase
	from poker.statistics.database.postgres_repositories import (
		PostgresPlayerRepository,
		PostgresStatisticsRepository,
		PostgresMemoryRepository,
	)
	from poker.statistics.database.services import StatisticsService
	from poker.statistics.database.facade import StatisticsFacade

	db_url = os.getenv("POKER_DATABASE_URL")
	if not db_url:
		return None, None

	engine = create_engine(db_url)
	DeclarativeBase.metadata.create_all(engine)
	Session = sessionmaker(engine)
	session = Session()

	service = StatisticsService(
		player_repository=PostgresPlayerRepository(session),
		statistics_repository=PostgresStatisticsRepository(session),
		memory_repository=PostgresMemoryRepository(session),
	)
	return session, StatisticsFacade(service)

def main():
	parser = argparse.ArgumentParser(description="Run Self-Play data generation using RLDatasetCapture")
	parser.add_argument("--current-model", required=True, help="Path to the current neural model weights (.pt)")
	parser.add_argument("--pool-dir", required=True, help="Directory containing historical models")
	parser.add_argument("--output", required=True, help="Path to output JSONL dataset")
	parser.add_argument("--hands", type=int, default=1000, help="Number of hands to play")
	parser.add_argument("--seed", type=int, default=42, help="Random seed")
	parser.add_argument("--starting-stack", type=int, default=200, help="Starting stack for each player")
	parser.add_argument("--profile-scope", choices=["private", "global", "combined"], default="private", help="Scope of the opponent profiles given to the NeuralAgent")
	parser.add_argument("--table-size", type=int, default=2, choices=[2, 6], help="Number of players at the table (2 for Heads-Up, 6 for 6-max)")

	args = parser.parse_args()

	session, facade = setup_statistics()

	from poker.learning.observation import LearningObservationEncoder
	from poker.statistics.opponent_profile import OpponentProfileProvider
	from poker.agents import RandomAgent, CallingStationAgent, NitAgent, ManiacAgent, TAGAgent, LAGAgent
	import random

	provider = OpponentProfileProvider(facade) if facade else None
	obs_encoder = LearningObservationEncoder(profile_provider=provider)

	pool = ModelPool(args.pool_dir)
	historical_model_path = pool.sample_model(seed=args.seed)

	# Agent 1: The model currently being trained
	agents = {}
	agent_ids = {}

	agents["current"] = NeuralAgent(
		model_path=args.current_model,
		stochastic=True,
		agent_id="current",
		observation_encoder=obs_encoder,
		profile_scope=args.profile_scope
	)
	agent_ids["current"] = "current"

	# Agent 2: Historical model (or self if pool is empty)
	if historical_model_path is None:
		print("No historical models found. Using current model as opponent.")
		historical_model_path = args.current_model

	agents["historical"] = NeuralAgent(
		model_path=str(historical_model_path),
		stochastic=True,
		agent_id="historical",
		observation_encoder=obs_encoder,
		profile_scope=args.profile_scope
	)
	agent_ids["historical"] = "historical"

	# Agents 3-6: Heuristic bots from the DB pool (if 6-max)
	if args.table_size == 6:
		print("Setting up 6-max table...")
		available_bots = []
		if facade:
			from poker.statistics.database.sqlalchemy_models import PlayerModel
			db_players = facade.service.player_repository.session.query(PlayerModel).all()
			available_bots = [p.name for p in db_players if p.name not in ("current", "historical")]

		random.seed(args.seed)

		for i in range(4):
			bot_name = f"random_bot_{i}"
			if available_bots:
				bot_name = random.choice(available_bots)
				available_bots.remove(bot_name)

			agent_ids[bot_name] = bot_name

			if bot_name.startswith("tag"):
				agents[bot_name] = TAGAgent(seed=args.seed + i)
			elif bot_name.startswith("maniac"):
				agents[bot_name] = ManiacAgent(seed=args.seed + i)
			elif bot_name.startswith("lag"):
				agents[bot_name] = LAGAgent(seed=args.seed + i)
			elif bot_name.startswith("nit"):
				agents[bot_name] = NitAgent()
			elif bot_name.startswith("calling_station"):
				agents[bot_name] = CallingStationAgent()
			else:
				agents[bot_name] = RandomAgent(seed=args.seed + i)

	output_path = Path(args.output)
	if output_path.exists():
		output_path.unlink()

	writer = LearningDatasetWriter(output_path)

	capture = RLDatasetCapture(
		writer=writer,
		include_players=["current", "historical"], # We only want to learn from our neural bots, not the heuristics
		agent_ids=agent_ids,
		profile_scope=args.profile_scope
	)

	from poker.statistics.online_tracker import OnlineMemoryTracker
	tracker = OnlineMemoryTracker(statistics_facade=facade) if facade else None

	def composite_hand_observer(history):
		capture.hand_observer(history)
		if tracker:
			tracker.process_hand(history)

	runner = ArenaRunner(
		agents=agents,
		starting_stack=args.starting_stack,
		statistics_service=facade.service if facade else None,
		decision_observer=capture.decision_observer,
		hand_observer=composite_hand_observer
	)

	print(f"Starting {args.table_size}-max Self-Play Arena for {args.hands} hands...")
	stats = runner.run(hands=args.hands, seed=args.seed)

	print(json.dumps({
		"hands_played": stats.hands,
		"failed_hands": stats.failed_hands,
		"current_model": args.current_model,
		"historical_model": str(historical_model_path),
		"output": args.output,
	}, indent=2))

	if session:
		session.close()

if __name__ == "__main__":
	main()
