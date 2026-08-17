import torch

from poker.api import ActionDecision
from poker.game.actions import PlayerAction

class NeuralAgent:
	def __init__(
		self,
		model_path,
		observation_encoder=None,
		action_encoder=None,
		device="cpu",
		stochastic=False,
	):
		from poker.learning.actions import LearningActionEncoder
		from poker.learning.model import PokerPolicyNetwork
		from poker.learning.observation import LearningObservationEncoder

		self.device = device
		self.observation_encoder = observation_encoder or LearningObservationEncoder()
		self.action_encoder = action_encoder or LearningActionEncoder()
		self.stochastic = stochastic

		state_dict = torch.load(model_path, map_location=device, weights_only=True)
		input_size = state_dict["feature_extractor.0.weight"].size(1)

		self.model = PokerPolicyNetwork(observation_size=input_size)
		self.model.load_state_dict(state_dict)
		self.model.to(device)
		self.model.eval()

	def choose_action(self, state, legal):
		observation = self.observation_encoder.encode(state, profile_scope="global")
		action_space = self.action_encoder.encode(legal, state)

		obs_tensor = torch.tensor(observation.values, dtype=torch.float32).unsqueeze(0).to(self.device)
		mask_tensor = torch.tensor(action_space.mask, dtype=torch.float32).unsqueeze(0).to(self.device)

		with torch.no_grad():
			outputs = self.model(obs_tensor, action_mask=mask_tensor)
			action_logits = outputs["action_logits"]
			sizing_val = outputs["sizing"].item()

		if self.stochastic:
			dist = torch.distributions.Categorical(logits=action_logits[0])
			action_index = dist.sample().item()
		else:
			action_index = action_logits.argmax(dim=-1).item()

		action_name = self.action_encoder.ACTION_NAMES[action_index]

		action_enum = None
		for action in legal.actions:
			if action.value == action_name:
				action_enum = action
				break

		if action_enum is None:
			# Fallback if argmax somehow picked an illegal action (should be masked)
			action_enum = PlayerAction.FOLD if PlayerAction.FOLD in legal.actions else legal.actions[0]
			return ActionDecision(action_enum, 0)

		amount = 0
		scale = self.action_encoder._scale(state)

		if action_enum == PlayerAction.CALL:
			amount = legal.call_amount
		elif action_enum == PlayerAction.BET:
			raw_amount = int(sizing_val * scale)
			amount = max(legal.min_bet, min(legal.max_bet, raw_amount))
		elif action_enum == PlayerAction.RAISE:
			raw_amount = int(sizing_val * scale)
			amount = max(legal.min_raise_to, min(legal.max_raise_to, raw_amount))

		return ActionDecision(action_enum, amount)
