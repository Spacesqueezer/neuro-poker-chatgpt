from dataclasses import dataclass
from enum import Enum


class SeatStatus(str, Enum):
	ACTIVE = "active"
	SITTING_OUT = "sitting_out"
	BUSTED = "busted"


@dataclass
class Seat:
	index: int
	player: object
	status: SeatStatus = SeatStatus.ACTIVE

	def is_eligible(self):
		return self.status == SeatStatus.ACTIVE and self.player.chips > 0


class Table:
	def __init__(self):
		self.seats = []
		self.dealer_button_seat_index = None

	def add_player(self, player):
		if self.seat_for_player(player) is not None:
			raise ValueError("Player is already seated")

		seat = Seat(len(self.seats), player)
		self.seats.append(seat)
		return seat

	def seat_for_player(self, player):
		for seat in self.seats:
			if seat.player is player:
				return seat
		return None

	def sync_statuses(self):
		for seat in self.seats:
			if seat.status == SeatStatus.ACTIVE and seat.player.chips <= 0:
				seat.status = SeatStatus.BUSTED

	def hand_seats(self):
		self.sync_statuses()
		return [seat for seat in self.seats if seat.is_eligible()]

	def hand_players(self):
		return [seat.player for seat in self.hand_seats()]

	def sit_out(self, player):
		seat = self._require_seat(player)
		if seat.status == SeatStatus.BUSTED:
			raise ValueError("Busted player cannot sit out")
		seat.status = SeatStatus.SITTING_OUT

	def sit_in(self, player):
		seat = self._require_seat(player)
		if player.chips <= 0:
			seat.status = SeatStatus.BUSTED
			raise ValueError("Player needs chips to sit in")
		seat.status = SeatStatus.ACTIVE

	def mark_busted(self, player):
		seat = self._require_seat(player)
		seat.status = SeatStatus.BUSTED

	def set_button_player(self, player):
		seat = self._require_seat(player)
		self.dealer_button_seat_index = seat.index
		return seat.index

	def advance_button(self):
		eligible = self.hand_seats()
		if not eligible:
			raise ValueError("Cannot advance dealer button without active funded seats")

		if self.dealer_button_seat_index is None:
			self.dealer_button_seat_index = eligible[0].index
			return self.dealer_button_seat_index

		seat_count = len(self.seats)
		for offset in range(1, seat_count + 1):
			index = (self.dealer_button_seat_index + offset) % seat_count
			if self.seats[index].is_eligible():
				self.dealer_button_seat_index = index
				return index

		raise ValueError("Cannot advance dealer button without active funded seats")

	def button_player(self):
		if self.dealer_button_seat_index is None:
			return None
		return self.seats[self.dealer_button_seat_index].player

	def _require_seat(self, player):
		seat = self.seat_for_player(player)
		if seat is None:
			raise ValueError("Player is not seated")
		return seat
