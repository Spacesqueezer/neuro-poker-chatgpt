import torch
import torch.nn as nn


class PokerPolicyNetwork(nn.Module):
	def __init__(self, observation_size, action_classes=6, hidden_sizes=(256, 128)):
		super().__init__()

		self.observation_size = observation_size
		self.action_classes = action_classes

		layers = []
		input_dim = observation_size
		for hidden_dim in hidden_sizes:
			layers.append(nn.Linear(input_dim, hidden_dim))
			layers.append(nn.ReLU())
			input_dim = hidden_dim

		self.feature_extractor = nn.Sequential(*layers)
		self.action_head = nn.Linear(input_dim, action_classes)

		self.sizing_head = nn.Linear(input_dim, 1)
		self.value_head = nn.Linear(input_dim, 1)

	def forward(self, observation, action_mask=None):
		features = self.feature_extractor(observation)
		action_logits = self.action_head(features)

		if action_mask is not None:
			# Mask illegal actions by adding a large negative number
			# Mask values are 1 for legal, 0 for illegal
			illegal_mask = 1.0 - action_mask
			action_logits = action_logits - 1e9 * illegal_mask

		# Sizing is strictly a ratio [0.0, 1.0]
		sizing_output = torch.sigmoid(self.sizing_head(features)).squeeze(-1)

		# Expected reward (unbounded chips)
		value_output = self.value_head(features).squeeze(-1)

		return {
			"action_logits": action_logits,
			"sizing": sizing_output,
			"value": value_output,
		}
