class HandTracker:
    """
    Stateful tracker across multiple frames to remember player names and stacks
    even when their seat box displays an action (like FOLD or CHECK).
    """
    def __init__(self):
        self.players_state = {}

    def update_frame(self, parsed_players):
        """
        Takes a list of parsed player dictionaries from a single frame and updates the state.
        Returns the merged state.
        """
        for p in parsed_players:
            seat = p["seat"]

            # Initialize seat if not present
            if seat not in self.players_state:
                self.players_state[seat] = {
                    "name": None,
                    "stack": None,
                    "last_action": None
                }

            current = self.players_state[seat]

            # If the parser found a name/stack, update our memory
            if p["name"] is not None:
                current["name"] = p["name"]

            if p["stack"] is not None:
                current["stack"] = p["stack"]

            # Always update the action (can be None if it disappeared)
            current["last_action"] = p["action"]

        return self.players_state

    def reset_hand(self):
        """Called when a new hand starts to clear actions, but can retain names/stacks."""
        for seat in self.players_state:
            self.players_state[seat]["last_action"] = None
