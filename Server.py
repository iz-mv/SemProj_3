import socket
import pickle
from datetime import datetime
import time
from threading import Thread, Timer
import random

from utils import save_grid_to_image

BUFFER_SIZE = 1024
room_name = '012'
field_size = 16
timer = 10
themes = ["Flower", "Sunrise", "Waterfall", "House", "Lake", "Forest", "Apple", "Star", "City"]
timer2 = 10

class Broadcast(Thread):
	def __init__(self, client, rooms):
		super().__init__(daemon=True)
		self.all_rooms = rooms
		self.client = client
		self.room = self.all_rooms.get('0')
		self.room.add_user(self)
		self.packet_template = {"body": '', 'msgtype': ''}
		self.start()

	def run(self) -> None:
		while True:
			data_in_bytes = self.recv()
			data: dict = pickle.loads(data_in_bytes)

			packet = data.copy()
			match data['msgtype']:
				case 'chat':
					print('got signal of chat', data)
				# implement
				case 'game':
					print('got signal of game', data)
					if self.room.room_name == "0":
						continue
					elif data.get('body'):
						x, y = data.get('body')
						status = self.room.game.move(x, y, self.client.color)
						if status:
							packet['body'] = (str(x), str(y), self.client.color)
							print('done')
						else:
							self.send_text_from_server("The number of players is not enough")
							continue

				case 'color':
					if self.room.room_name == '0':
						continue
					self.client.color = data.get('body')
					continue
				case "name":
					print(f"Changing username for {self.client.username} to {data.get('body')}")
					self.client.change_username(data.get('body'))  # Изменяем имя только для текущего клиента
					continue
				case 'save_image':
					self.save_image()
					continue
				case 'room':
					self.room_changer(data['body'])
					print('got signal of room', data)

			for user in self.room.users:  # type: ClientHandler
				print('send to client', user)
				if packet['msgtype'] == 'room':
					user.send_text_from_server(f"Welcome {self.client.username}")
				if packet['msgtype'] == 'chat':
					packet = data.copy()
					prefix = "From YOU: " if user == self else f"From {user.client.username}: "
					packet['body'] = prefix + packet.get('body')
					print(packet.get('body'))
				if packet['msgtype'] != 'room':
					data_in_bytes: bytes = pickle.dumps(packet)
					user.send(data_in_bytes)

	def save_image(self):
		filename = f"game_field_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
		save_grid_to_image(self.room.game.game_field, filename)
		# with open(filename, "rb") as file:
		# 	file = file.read()
		# 	file_object = {'filename': 'example.txt','data': file}
		# 	data = self.packet_template.copy()
		# 	data['msgtype'] = 'save_image'
		# 	data['body'] = file_object
		# 	self.send(pickle.loads(data))
		self.send_text_from_server(f"Game field saved as {filename}")

	def room_changer(self, new_room):
		self.room.delete_user(self)
		self.room = self.all_rooms.get(new_room)
		if not self.room.add_user(self):
			self.send_text_from_server("the room is busy, please wait in the lobby")
			self.room = self.all_rooms.get('0')
			self.room.add_user(self)
		self.client.color = "#000000"

	def recv(self) -> bytearray:
		try:
			result = bytearray()
			while True:
				data: bytes = self.client.conn.recv(BUFFER_SIZE)
				result.extend(data)
				if result.endswith(Server.STOP):
					break
			return result[:-3]

		except ConnectionResetError:
			print(f"Client {self.client.username} disconnected unexpectedly")
			self.room.delete_user(self)  # Удаляем игрока из комнаты

	def send_text_from_server(self, msg: str):
		packet = {"body": '', 'msgtype': ''}
		packet['body'] = "From SERVER: " + msg
		packet['msgtype'] = 'chat'
		self.send(pickle.dumps(packet))

	def send(self, msg: bytes):
		self.client.conn.send(msg + Server.STOP)

	def game_ended(self):
		self.send_text_from_server("The game is ended, your image is saved")
		countdown = Timer(timer2, self.game_exit)
		countdown.start()

	def game_exit(self):
		self.room_changer('0')
		data = self.packet_template.copy()
		data['msgtype'] = 'game_end'
		data['body'] = '0'
		data_in_bytes = pickle.dumps(data)
		print("sended")
		self.send(data_in_bytes)




class ClientHandler:
	def __init__(self, connection: socket.socket, rooms):
		self.conn = connection
		self.username = "Nameless"
		self.broadcast = Broadcast(self, rooms)
		self.address: tuple = connection.getpeername()
		self.color = "#000000"

	def change_username(self, name: str):
		self.username = name
		print(f"changed to {name}")


class Game:
	def __init__(self, players, room):
		self.room = room
		self.players = players
		self.game_field = [['#FFFFFF' for _ in range(field_size)] for _ in range(field_size)]
		self.status = False
		self.theme = random.choice(themes)
		self.game_not_blocked = True

	def move(self, x, y, color):
		print(self.players)
		if self.status:
			self.game_field[x][y] = color
			return True
		else:
			return False

	def game_start(self):
		self.status = True
		for player in self.players:
			player.send_text_from_server(f"The game is started, your theme is {self.theme}")
		countdown = Timer(timer, self.game_end)
		countdown.start()
		# логика запуска игры

	def game_end(self):
		self.status = False
		filename = f"game_field_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
		save_grid_to_image(self.game_field, filename)
		for player in self.players:
			player.game_ended()
		self.theme = random.choice(themes)
		print(f"[INFO] Room {self.room}: round finished, image saved to {filename}")
		self.game_field = [['#FFFFFF' for _ in range(field_size)] for _ in range(field_size)]





class Room:
	def __init__(self, room_name):
		self.room_name = room_name
		self.users = []
		if self.room_name != '0':
			self.game = Game(self.users, room_name)

	def add_user(self, user):
		if len(self.users) < 2 or self.room_name == '0':
			self.users.append(user)
			print('added', self.users)
			self.check_game_status()
			return True
		else:
			return False
		
	def delete_user(self, user):
		self.users.remove(user)
		self.check_game_status()

	def check_game_status(self):
		if self.room_name != '0':
			if len(self.users) == 2:
				self.game.status = True
				self.game.game_start()
			elif len(self.users) < 2 and self.game.status:
				self.game.game_end()


class Server:
	STOP = b'///'

	def __init__(self, host, port):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.sock.bind((host, port))
		self.sock.listen(2)
		self.all_clients = []

		self.rooms: dict[str, set[Room]] = {
			name: Room(name) for name in room_name
		}

	def serve_forever(self):
		while True:
			print('Waiting for connection')
			client_socket, client_address = self.sock.accept()
			print('Connection from', client_address)
			self.all_clients.append(ClientHandler(client_socket, self.rooms))


server = Server('localhost', 9000)
server.serve_forever()