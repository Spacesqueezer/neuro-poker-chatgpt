import argparse
import subprocess
import json
from pathlib import Path
import sys

def run_command(cmd, description):
	print(f"\n--- {description} ---")
	print(f"Running: {' '.join(cmd)}")
	result = subprocess.run(cmd)
	if result.returncode != 0:
		print(f"Command failed with exit code {result.returncode}")
		sys.exit(result.returncode)

def main():
	parser = argparse.ArgumentParser(description="Automate the Self-Play -> Train -> Evaluate -> Promote loop")
	parser.add_argument("--pool-dir", required=True, help="Directory for model pool")
	parser.add_argument("--iterations", type=int, default=10, help="Number of RL loop iterations")
	parser.add_argument("--hands", type=int, default=1000, help="Hands per self-play generation")
	parser.add_argument("--epochs", type=int, default=5, help="Training epochs per iteration")
	args = parser.parse_args()

	pool_dir = Path(args.pool_dir)
	pool_dir.mkdir(parents=True, exist_ok=True)

	# Try to find an initial model. If pool is empty, we'd ideally bootstrap one.
	# For orchestration demo, assume pool/policy_v0.pt exists or we expect user to bootstrap it.
	models = sorted(pool_dir.glob("*.pt"))
	if not models:
		print(f"Error: No initial model found in {pool_dir}. Please bootstrap a policy_v0.pt.")
		sys.exit(1)

	current_model = models[-1]

	for iteration in range(1, args.iterations + 1):
		print(f"\n========== ITERATION {iteration} ==========")

		# 1. Generate Dataset
		dataset_path = pool_dir.parent / "datasets" / f"self_play_iter_{iteration}.jsonl"
		run_command([
			sys.executable, "tools/run_self_play.py",
			"--current-model", str(current_model),
			"--pool-dir", str(pool_dir),
			"--output", str(dataset_path),
			"--hands", str(args.hands)
		], "Generate Self-Play Data")

		# 2. Train Network
		# For true RL we'd use a different trainer, but we map to train_imitation for now as a placeholder
		# since train_rl.py is not strictly written yet in this step, but the orchestration logic is what matters.
		new_model_path = pool_dir / f"policy_v{iteration}.pt"
		run_command([
			sys.executable, "tools/train_imitation.py",
			"--train", str(dataset_path),
			"--validation", str(dataset_path),
			"--output", str(new_model_path),
			"--epochs", str(args.epochs)
		], "Train Network")

		# 3. Evaluate vs Baseline
		benchmark_out = pool_dir.parent / "artifacts" / f"benchmark_iter_{iteration}.json"
		run_command([
			sys.executable, "tools/benchmark_neural.py",
			"--model", str(new_model_path),
			"--opponents", "random",
			"--hands", "500",
			"--output", str(benchmark_out)
		], "Evaluate Model")

		# In a real setup, we'd parse the benchmark output and only "Promote" if winrate > threshold.
		# For this orchestrator skeleton, we assume promotion by setting current_model.
		print(f"Promoted {new_model_path.name} as the new current model.")
		current_model = new_model_path

if __name__ == "__main__":
	main()
