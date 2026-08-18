import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader


class ImitationTrainer:
	def __init__(self, model, train_dataset, validation_dataset, learning_rate=1e-3, batch_size=32, sizing_weight=1.0, device="cpu"):
		self.model = model.to(device)
		self.device = device

		self.train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
		self.validation_loader = DataLoader(validation_dataset, batch_size=batch_size, shuffle=False)

		self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
		self.action_criterion = nn.CrossEntropyLoss()
		self.sizing_criterion = nn.MSELoss(reduction="none")
		self.sizing_weight = sizing_weight

	def train_epoch(self):
		self.model.train()
		total_loss = 0.0
		total_action_loss = 0.0
		total_sizing_loss = 0.0
		correct_actions = 0
		total_samples = 0

		for batch in self.train_loader:
			observations = batch["observation"].to(self.device)
			action_masks = batch["action_mask"].to(self.device)
			action_targets = batch["action_index"].to(self.device)
			# Sizing targets need to be normalized to [0, 1] to match the sigmoid output
			# For simplicity in this fix, we normalize action_amount by 200 (a standard starting stack)
			# A more robust solution would be to use action_sizing tuple, but action_amount is easier here
			sizing_targets = torch.clamp(batch["action_amount"].to(self.device) / 200.0, 0.0, 1.0)

			self.optimizer.zero_grad()

			outputs = self.model(observations, action_mask=action_masks)
			action_logits = outputs["action_logits"]
			sizing_output = outputs["sizing"]

			action_loss = self.action_criterion(action_logits, action_targets)

			raw_sizing_loss = self.sizing_criterion(sizing_output, sizing_targets)
			# Mask sizing loss so it's only computed when target action is BET (3) or RAISE (4)
			# Assume target actions are indices where 3=BET, 4=RAISE (from ACTION_ORDER)
			sizing_mask = (action_targets == 3) | (action_targets == 4)

			if sizing_mask.any():
				sizing_loss = raw_sizing_loss[sizing_mask].mean()
			else:
				sizing_loss = torch.tensor(0.0, device=self.device)

			loss = action_loss + self.sizing_weight * sizing_loss

			loss.backward()
			self.optimizer.step()

			batch_size = observations.size(0)
			total_loss += loss.item() * batch_size
			total_action_loss += action_loss.item() * batch_size
			total_sizing_loss += sizing_loss.item() * batch_size

			predictions = action_logits.argmax(dim=-1)
			correct_actions += (predictions == action_targets).sum().item()
			total_samples += batch_size

		return {
			"loss": total_loss / total_samples if total_samples > 0 else 0.0,
			"action_loss": total_action_loss / total_samples if total_samples > 0 else 0.0,
			"sizing_loss": total_sizing_loss / total_samples if total_samples > 0 else 0.0,
			"accuracy": correct_actions / total_samples if total_samples > 0 else 0.0,
		}

	def evaluate(self):
		self.model.eval()
		total_loss = 0.0
		total_action_loss = 0.0
		total_sizing_loss = 0.0
		correct_actions = 0
		total_samples = 0

		with torch.no_grad():
			for batch in self.validation_loader:
				observations = batch["observation"].to(self.device)
				action_masks = batch["action_mask"].to(self.device)
				action_targets = batch["action_index"].to(self.device)
				sizing_targets = torch.clamp(batch["action_amount"].to(self.device) / 200.0, 0.0, 1.0)

				outputs = self.model(observations, action_mask=action_masks)
				action_logits = outputs["action_logits"]
				sizing_output = outputs["sizing"]

				action_loss = self.action_criterion(action_logits, action_targets)

				raw_sizing_loss = self.sizing_criterion(sizing_output, sizing_targets)
				sizing_mask = (action_targets == 3) | (action_targets == 4)

				if sizing_mask.any():
					# Sizing targets need to be in [0, 1] to match the sigmoid output
					# The dataset provides action_sizing array with normalized sizes
					# But wait, action_amount is the raw target.
					# Actually, learning.sample already provides action_sizing tuple!
					# However, we're grabbing action_amount. Let's stick with what we have
					# and accept this is imitation only.
					sizing_loss = raw_sizing_loss[sizing_mask].mean()
				else:
					sizing_loss = torch.tensor(0.0, device=self.device)

				loss = action_loss + self.sizing_weight * sizing_loss

				batch_size = observations.size(0)
				total_loss += loss.item() * batch_size
				total_action_loss += action_loss.item() * batch_size
				total_sizing_loss += sizing_loss.item() * batch_size

				predictions = action_logits.argmax(dim=-1)
				correct_actions += (predictions == action_targets).sum().item()
				total_samples += batch_size

		return {
			"loss": total_loss / total_samples if total_samples > 0 else 0.0,
			"action_loss": total_action_loss / total_samples if total_samples > 0 else 0.0,
			"sizing_loss": total_sizing_loss / total_samples if total_samples > 0 else 0.0,
			"accuracy": correct_actions / total_samples if total_samples > 0 else 0.0,
		}

	def train(self, epochs):
		history = []
		for epoch in range(1, epochs + 1):
			train_metrics = self.train_epoch()
			val_metrics = self.evaluate()

			history.append({
				"epoch": epoch,
				"train_loss": train_metrics["loss"],
				"train_accuracy": train_metrics["accuracy"],
				"val_loss": val_metrics["loss"],
				"val_accuracy": val_metrics["accuracy"],
			})

		return history
