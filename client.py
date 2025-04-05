import socket
import pickle
import sys
from threading import Thread
from queue import SimpleQueue

from gui_1 import Ui_MainWindow
from PyQt6.QtCore import pyqtSlot, pyqtSignal, QObject
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QGridLayout, QPushButton,
    QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QMessageBox, QTextEdit,
    QColorDialog)
from PyQt6.QtGui import QColor

BUFFER_SIZE = 1024


class GUICommunication(QObject):
	chat_updating_signal = pyqtSignal(str)
	game_updating_signal = pyqtSignal(int, int, str)
	room_changing_signal = pyqtSignal()
	name_updating_signal = pyqtSignal(str)

class MainWindow(QMainWindow, Ui_MainWindow):
	def __init__(self, username):
		super().__init__()
		self.setupUi(self)
		self.setWindowTitle("Pixel Battle")
		self.username = username
		self.gui_communication = GUICommunication()
		self.socket_communication = SocketCommunication('localhost', 9000, self.gui_communication, username)
		self.send_msg_btn.clicked.connect(self.btn_send_logic)
		self.btn_rooms = [self.lobby_btn, self.room1_btn, self.room2_btn,]
		for index, btn_room in enumerate(self.btn_rooms, 0):
			btn_room.clicked.connect(lambda state, ROOM=index: self.room_change_logic(ROOM))

		self.gui_communication.chat_updating_signal.connect(self.chat_updating_logic)
		self.gui_communication.game_updating_signal.connect(lambda x, y, color: self.game_updating_logic(x, y, color))
		# self.gui_communication.name_updating_signal.connect(lambda: self.change_name_logic())


		self.buttons = {}
		self.grid_width = 16  # Ширина сетки
		self.grid_height = 16  # Высота сетки
		for y in range(self.grid_height):
			for x in range(self.grid_width):
				btn = QPushButton('')
				btn.setFixedSize(24, 24)
				btn.setStyleSheet("background-color: #FFFFFF; border: 1px solid #CCC; padding: 0; margin: 0;")
				btn.clicked.connect(lambda state, X=x, Y=y: self.btn_game_logic(X, Y))
				self.game_layout.addWidget(btn, y, x)
				self.buttons[(x, y)] = btn
		self.show()
		self.chs_clr_btn.setEnabled(True)
		self.chs_clr_btn.clicked.connect(self.choose_color)
		self.connect_btn.setEnabled(True)
		self.connect_btn.clicked.connect(lambda: self.change_name_logic())
		self.save_pic_btn.clicked.connect(self.save_picture_logic)
		self.gui_communication.room_changing_signal.connect(self.game_field_clear)


	@pyqtSlot(str)
	def chat_updating_logic(self, txt: str):
		self.chat_field.append(txt)

	@pyqtSlot(int, int)
	def game_updating_logic(self, x: int, y: int, color):
		cell = self.buttons[(x, y)]
		cell.setStyleSheet(f'background-color: {color};')
		# cell.setEnabled(False)
		print('colored')

	@pyqtSlot()
	def btn_send_logic(self):
		text = self.chat_line.text()
		self.socket_communication.send_data_queue.put(('chat', text))
		self.chat_line.setText('')

	@pyqtSlot(int, int)
	def btn_game_logic(self, x: int, y: int):
		self.socket_communication.send_data_queue.put(('game', (x, y)))
		print(f'send {x}, {y}')

	@pyqtSlot(int)
	def room_change_logic(self, room_index: int):
		self.game_field_clear()
		self.socket_communication.send_data_queue.put(('room', str(room_index)))

	@pyqtSlot()
	def choose_color(self):
		dlg = QColorDialog(self)
		if dlg.exec():
			chosen = dlg.selectedColor()
			if chosen.isValid():
				color = chosen.name()
				self.socket_communication.send_data_queue.put(("color", color))

	@pyqtSlot()
	def change_name_logic(self):
		new_name = self.name_line.text().strip()
		if new_name:
			self.socket_communication.send_data_queue.put(("name", new_name))
		self.name_line.setText("")


	@pyqtSlot()
	def save_picture_logic(self):
		self.socket_communication.send_data_queue.put(('save_image', ''))

	@pyqtSlot()
	def game_field_clear(self):
		print("clearing")
		self.chat_field.clear()
		for y in range(self.grid_height):
			for x in range(self.grid_width):
				cell = self.buttons[(x, y)]
				cell.setStyleSheet('background-color: #FFFFFF')



class SocketCommunication:
	STOP = b'///'

	def __init__(self, host, port, gui_communication: GUICommunication, username):
		self.send_data_queue = SimpleQueue()
		self.gui_communication: GUICommunication = gui_communication

		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		print('Socket created')
		self.sock.connect((host, port))
		print('Socket connected')

		# packet = {'msgtype': 'name', 'body': username}
		# data_in_bytes: bytes = pickle.dumps(packet)
		# self.send(data_in_bytes)

		Thread(target=self.send_data_stream_daemon, daemon=True).start()
		Thread(target=self.recv_data_stream_daemon, daemon=True).start()

	def recv(self) -> bytearray:
		result = bytearray()
		while True:
			data: bytes = self.sock.recv(BUFFER_SIZE)
			result.extend(data)
			if result.endswith(SocketCommunication.STOP):
				break
		return result[:-3]

	def send_text(self, msg: str):
		packet = {'msgtype': 'chat', 'body': msg}
		data_in_bytes: bytes = pickle.dumps(packet)
		self.sock.send(data_in_bytes + SocketCommunication.STOP)

	def send(self, msg: bytes):
		self.sock.send(msg + SocketCommunication.STOP)

	def send_data_stream_daemon(self):
		while True:
			# wait the data from GUI which we need to send to server
			msgtype, body = self.send_data_queue.get(block=True)
			# form the "packet" (our protocol) for sending to server
			packet = dict(msgtype=msgtype, body=body)
			# send it in BYTES by using dumps -> using serialization
			self.send(pickle.dumps(packet))

	def recv_data_stream_daemon(self):
		while True:
			# get the answer from server which we need to send to GUI
			answer_in_bytes: bytes = self.recv()
			# convert the bytes into the object by using loads -> deserealization
			data: dict = pickle.loads(answer_in_bytes)
			# extract the information from it, choose what to do
			msgtype = data['msgtype']
			body = data['body']
			match msgtype:
				case 'chat':
					self.gui_communication.chat_updating_signal.emit(body)
				case 'game':
					x, y, color = body # type: int, int, str
					print(f"recived {x, y, color}")
					self.gui_communication.game_updating_signal.emit(int(x), int(y), color)
					# self.send_text(f'button {x, y} was pressed')
				case 'room':
					print('kek, server will not send this :D (but we can)')
				case "game_end":
					print("got a signal of endgame")
					self.gui_communication.room_changing_signal.emit()
				# case 'save_image':
				# 	file_object = body
				# 	with open(file_object['filename'], 'wb') as file:
				# 		file.write(file_object['data'])


name = sys.argv[1]
app = QApplication([])
window = MainWindow(name)
app.exec()