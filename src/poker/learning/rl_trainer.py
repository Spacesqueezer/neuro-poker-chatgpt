import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader


class PolicyGradientTrainer:
	def __init__(self, model, train_dataset, learning_rate=1e-4, batch_size=32, value_weight=0.5, entropy_weight=0.01, device="cpu"):
		self.model = model.to(device)
		self.device = device

		# For RL, we might only have a train dataset generated from recent self-play
		self.train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

		self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
		self.value_criterion = nn.MSELoss()

		self.value_weight = value_weight
		self.entropy_weight = entropy_weight

	def train_epoch(self):
		self.model.train()
		total_loss = 0.0
		total_pg_loss = 0.0
		total_value_loss = 0.0
		total_entropy = 0.0
		total_samples = 0

		for batch in self.train_loader:
			observations = batch["observation"].to(self.device)
			action_masks = batch["action_mask"].to(self.device)
			action_targets = batch["action_index"].to(self.device) # The action actually taken
			sizing_targets = torch.clamp(batch["action_amount"].to(self.device), 0.0, 1.0)
			rewards = batch["reward"].to(self.device)

			self.optimizer.zero_grad()

			outputs = self.model(observations, action_mask=action_masks)
			action_logits = outputs["action_logits"]
			sizing_preds = outputs["sizing"]
			value_preds = outputs["value"]

			# Value Loss: MSE(value_prediction, true_reward)
			value_loss = self.value_criterion(value_preds, rewards)

			# Policy Gradient Loss: -log_prob(action_taken) * Advantage
			# Advantage = Reward - Value Prediction (baseline)
			advantages = (rewards - value_preds.detach()) # detach so we don't backprop value head from policy loss

			# Get log probabilities of discrete actions
			log_probs = F.log_softmax(action_logits, dim=-1)

			# Gather the log prob of the action actually taken
			action_log_probs = log_probs.gather(dim=-1, index=action_targets.unsqueeze(-1)).squeeze(-1)

			# For sizing, we treat the output as the mean of a Normal distribution with fixed variance
			# This allows gradients to flow into the sizing head during RL
			# We only compute sizing log prob if the chosen action was BET (3) or RAISE (4)
			sizing_mask = (action_targets == 3) | (action_targets == 4)
			sizing_log_probs = torch.zeros_like(action_log_probs)

			if sizing_mask.any():
				# Normal distribution around predicted sizing with std=0.1 (exploration parameter)
				sizing_dist = torch.distributions.Normal(sizing_preds[sizing_mask], 0.1)
				# Log prob of the actual sizing chosen during self play
				sizing_log_probs[sizing_mask] = sizing_dist.log_prob(sizing_targets[sizing_mask])

			# Combined log prob (assuming conditional independence)
			total_log_probs = action_log_probs + sizing_log_probs

			# REINFORCE objective
			pg_loss = -(total_log_probs * advantages).mean()

			# Entropy bonus to encourage exploration
			probs = F.softmax(action_logits, dim=-1)
			entropy = -(probs * log_probs).sum(dim=-1).mean()

			# Total Loss
			loss = pg_loss + self.value_weight * value_loss - self.entropy_weight * entropy

			loss.backward()
			self.optimizer.step()

			batch_size = observations.size(0)
			total_loss += loss.item() * batch_size
			total_pg_loss += pg_loss.item() * batch_size
			total_value_loss += value_loss.item() * batch_size
			total_entropy += entropy.item() * batch_size
			total_samples += batch_size

		return {
			"loss": total_loss / total_samples if total_samples > 0 else 0.0,
			"pg_loss": total_pg_loss / total_samples if total_samples > 0 else 0.0,
			"value_loss": total_value_loss / total_samples if total_samples > 0 else 0.0,
			"entropy": total_entropy / total_samples if total_samples > 0 else 0.0,
		}

	def train(self, epochs):
		history = []
		for epoch in range(1, epochs + 1):
			metrics = self.train_epoch()

			history.append({
				"epoch": epoch,
				**metrics
			})

		return history
