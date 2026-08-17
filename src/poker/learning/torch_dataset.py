import json
from pathlib import Path

import torch
from torch.utils.data import Dataset

class PokerImitationDataset(Dataset):
	def __init__(self, path):
		self.path = Path(path)
		self.samples = []
		self._load()

	def _load(self):
		with self.path.open("r", encoding="utf-8") as f:
			for line in f:
				if not line.strip():
					continue
				payload = json.loads(line)
				self.samples.append(payload)

	def __len__(self):
		return len(self.samples)

	def __getitem__(self, idx):
		payload = self.samples[idx]

		# Strategy targets might be present if generated from solver teacher exports
		# For standard datasets, it might just be action_index

		# if "strategy" in payload: we might use KLDivLoss in future,
		# but for now we stick to simple CrossEntropy using action_index if available,
		# or argmax of strategy if "strategy" exists and "action_index" does not.

		action_index = payload.get("action_index", 0)

		return {
			"observation": torch.tensor(payload["observation"], dtype=torch.float32),
			"action_mask": torch.tensor(payload["action_mask"], dtype=torch.float32),
			"action_sizing": torch.tensor(payload["action_sizing"], dtype=torch.float32),
			"action_index": torch.tensor(action_index, dtype=torch.long),
			"action_amount": torch.tensor(payload.get("action_amount", 0.0), dtype=torch.float32),
			"reward": torch.tensor(payload.get("reward", 0.0), dtype=torch.float32),
		}
