import argparse
import json
import os
from pathlib import Path

from poker.agents import CallingStationAgent, NitAgent, RandomAgent, NeuralAgent, ManiacAgent, TAGAgent, LAGAgent
from poker.arena.runner import ArenaRunner

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

	engine = create_engine(db_url, pool_pre_ping=True, pool_recycle=3600)
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
	parser = argparse.ArgumentParser(description="Benchmark NeuralAgent against baselines")
	parser.add_argument("--model", required=True, help="Path to NeuralAgent .pt weights")
	parser.add_argument("--opponents", nargs="+", choices=["random", "calling_station", "nit", "maniac", "tag", "lag"], default=["random"])
	parser.add_argument("--hands", type=int, default=1000)
	parser.add_argument("--seed", type=int, default=42)
	parser.add_argument("--starting-stack", type=int, default=200)
	parser.add_argument("--profile-scope", choices=["private", "global", "combined"], default="private", help="Scope of the opponent profiles given to the NeuralAgent")
	parser.add_argument("--table-size", type=int, default=2, choices=[2, 6], help="Number of players at the table")
	parser.add_argument("--output", type=str)
	args = parser.parse_args()

	session, facade = setup_statistics()

	# Pass facade to observation encoder to use Opponent Profile
	from poker.learning.observation import LearningObservationEncoder
	from poker.statistics.opponent_profile import OpponentProfileProvider

	provider = OpponentProfileProvider(facade) if facade else None
	obs_encoder = LearningObservationEncoder(profile_provider=provider)

	neural_agent = NeuralAgent(
		model_path=args.model,
		agent_id="neural", # Must match the dictionary key used in ArenaRunner
		observation_encoder=obs_encoder,
		profile_scope=args.profile_scope
	)

	results = []

	from poker.statistics.online_tracker import OnlineMemoryTracker
	tracker = OnlineMemoryTracker(statistics_facade=facade) if facade else None

	import random
	if args.table_size == 2:
		# Original Heads-Up Benchmarking Logic
		for opponent_name in args.opponents:
			print(f"Benchmarking against {opponent_name} for {args.hands} hands...")

			if opponent_name == "random":
				opponent = RandomAgent(seed=args.seed)
			elif opponent_name == "calling_station":
				opponent = CallingStationAgent()
			elif opponent_name == "nit":
				opponent = NitAgent()
			elif opponent_name == "maniac":
				opponent = ManiacAgent(seed=args.seed)
			elif opponent_name == "tag":
				opponent = TAGAgent(seed=args.seed)
			elif opponent_name == "lag":
				opponent = LAGAgent(seed=args.seed)

			agents = {
				"neural": neural_agent,
				opponent_name: opponent
			}

			runner = ArenaRunner(
				agents,
				starting_stack=args.starting_stack,
				statistics_service=facade.service if facade else None,
				hand_observer=tracker.process_hand if tracker else None
			)
			stats = runner.run(hands=args.hands, seed=args.seed)

			# Simplistic evaluation
			neural_profit = stats.players["neural"].profit if "neural" in stats.players else 0
			bb_100 = stats.summary().get("bb_per_100", {}).get("neural", 0.0)

			results.append({
				"opponent": opponent_name,
				"hands": stats.hands,
				"failed_hands": stats.failed_hands,
				"neural_profit": neural_profit,
				"bb_per_100": bb_100,
			})
	else:
		# 6-max Benchmarking Logic
		print(f"Benchmarking in 6-max table against a mix of opponents for {args.hands} hands...")

		available_bots = []
		if facade:
			from poker.statistics.database.sqlalchemy_models import PlayerModel
			db_players = facade.service.player_repository.session.query(PlayerModel).all()
			available_bots = [p.name for p in db_players if p.name != "neural"]

		agents = {"neural": neural_agent}
		agent_ids = {"neural": "neural"}
		random.seed(args.seed)

		# We need 5 opponents to complete the 6-max table
		# If user provided fewer opponents, we'll repeat them or pull from the DB
		base_opponents = args.opponents * 5

		for i in range(5):
			bot_name = f"bot_{i}_{base_opponents[i]}"
			if available_bots:
				bot_name = random.choice(available_bots)
				available_bots.remove(bot_name)

			agent_ids[bot_name] = bot_name

			# Assign heuristic logic based on prefix
			if "tag" in bot_name:
				agents[bot_name] = TAGAgent(seed=args.seed + i)
			elif "maniac" in bot_name:
				agents[bot_name] = ManiacAgent(seed=args.seed + i)
			elif "lag" in bot_name:
				agents[bot_name] = LAGAgent(seed=args.seed + i)
			elif "nit" in bot_name:
				agents[bot_name] = NitAgent()
			elif "calling_station" in bot_name:
				agents[bot_name] = CallingStationAgent()
			else:
				agents[bot_name] = RandomAgent(seed=args.seed + i)

		runner = ArenaRunner(
			agents,
			starting_stack=args.starting_stack,
			statistics_service=facade.service if facade else None,
			hand_observer=tracker.process_hand if tracker else None
		)
		stats = runner.run(hands=args.hands, seed=args.seed)

		neural_profit = stats.players["neural"].profit if "neural" in stats.players else 0
		bb_100 = stats.summary().get("bb_per_100", {}).get("neural", 0.0)

		results.append({
			"opponent": "6_max_mix",
			"hands": stats.hands,
			"failed_hands": stats.failed_hands,
			"neural_profit": neural_profit,
			"bb_per_100": bb_100,
		})

	print("\nBenchmark Results:")
	print(json.dumps(results, indent=2))

	if args.output:
		output_path = Path(args.output)
		output_path.parent.mkdir(parents=True, exist_ok=True)
		output_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
		print(f"Results saved to {output_path}")

	if session:
		session.close()

if __name__ == "__main__":
	main()
