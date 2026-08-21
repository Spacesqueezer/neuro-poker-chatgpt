from poker.api.hand_state import HandStateView, LegalActions, PublicPlayerView
from poker.game.actions import PlayerAction
from poker.vision.state import ScreenState

class ScreenTranslator:
    """
    Транслятор преобразует "сырые" данные с экрана (ScreenState)
    в математические объекты покерного движка (HandStateView и LegalActions),
    которые ожидает на вход NeuralAgent.
    """

    def __init__(self, hero_name="Hero"):
        self.hero_name = hero_name

    def translate_state(self, screen: ScreenState) -> HandStateView:
        # Ищем дилера (баттон)
        dealer_name = ""
        for p in screen.players:
            if p.is_dealer:
                dealer_name = p.name
                break

        if not dealer_name and screen.players:
            dealer_name = screen.players[0].name # Fallback

        # Маппинг игроков
        # Для нейросети важны фишки и позиция.
        # В реальном парсинге определение SB и BB сложнее, тут базовая заглушка
        # В Фазе 8 мы добавим расчет позиций на основе баттона.
        players = []
        for p in screen.players:
            players.append(
                PublicPlayerView(
                    name=p.name,
                    chips=int(p.stack * 100), # Перевод в цент-блайнды, если стек был в $
                    current_bet=int(p.current_bet * 100),
                    total_contribution=int(p.current_bet * 100), # Временно
                    folded=not p.cards_dealt,
                    position="BTN" if p.is_dealer else "UNKNOWN" # ToDo: Calculate proper positions
                )
            )

        # Вычисляем target_bet (какую сумму нам надо уравнять)
        # Если call_amount_needed = 5, а мы уже поставили 2, значит цель = 7
        target_bet = 0
        for p in screen.players:
            if p.name == self.hero_name:
                target_bet = int((p.current_bet + screen.call_amount_needed) * 100)
                break

        return HandStateView(
            street=screen.street_name,
            acting_player=self.hero_name,
            hole_cards=tuple(screen.hero_hole_cards),
            board=tuple(screen.board_cards),
            pot=int(screen.total_pot * 100),
            target_bet=target_bet,
            minimum_raise=int(screen.min_raise_amount * 100) if screen.can_raise or screen.can_bet else 0,
            dealer=dealer_name,
            small_blind="SB", # ToDo
            big_blind="BB",   # ToDo
            players=tuple(players),
            action_history=() # Из зрения сложно восстановить полную историю раздачи, оставляем пустой
        )

    def translate_legal_actions(self, screen: ScreenState) -> LegalActions:
        actions = []

        if screen.can_fold:
            actions.append(PlayerAction.FOLD)
        if screen.can_check:
            actions.append(PlayerAction.CHECK)
        if screen.can_call:
            actions.append(PlayerAction.CALL)
        if screen.can_bet:
            actions.append(PlayerAction.BET)
        if screen.can_raise:
            actions.append(PlayerAction.RAISE)
        if screen.can_all_in:
            actions.append(PlayerAction.ALL_IN)

        # Защита от багов зрения: если мы должны делать ход, но нет доступных действий
        if not actions and screen.is_my_turn:
            actions = [PlayerAction.FOLD]

        return LegalActions(
            actions=tuple(actions),
            call_amount=int(screen.call_amount_needed * 100),
            min_bet=int(screen.min_raise_amount * 100) if screen.can_bet else None,
            max_bet=int(screen.max_raise_amount * 100) if screen.can_bet else None,
            min_raise_to=int(screen.min_raise_amount * 100) if screen.can_raise else None,
            max_raise_to=int(screen.max_raise_amount * 100) if screen.can_raise else None
        )
