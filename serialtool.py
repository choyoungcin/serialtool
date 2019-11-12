import fix_qt_import_error
import serial
from serial.tools import list_ports
import os
import sys
import threading
import time
from datetime import datetime
import shutil
import subprocess
import logging
import logging.config
import configparser
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

class MyTextEdit(QTextEdit):
	def __init__(self, parent = None):
		QTextEdit.__init__(self, parent)

	def contextMenuEvent(self, event):
		menu = QMenu(self)
		copy = menu.addAction('copy')
		selectAll = menu.addAction('Select all')
		hex2ascii = menu.addAction('Hex to ascii')
		action = menu.exec_(self.mapToGlobal(event.pos()))

		if action == hex2ascii:
			self.hexToAscii()

		elif action == copy:
			QTextEdit.copy(self)

		elif action == selectAll:
			QTextEdit.selectAll(self)

	def hexToAscii(self):
		text = self.textCursor().selectedText()
		try:
			text = text[text.index(']') + 1 :]
		except ValueError as e:
			#done nothing
			pass
		byteArray = text.strip().split(' ')
		asciiArray = []
		for i in byteArray:
			tmp = chr(int(i, 16))
			if not tmp.isprintable():
				asciiArray.append('.')
			else:
				asciiArray.append(tmp)
		
		self.append(''.join(asciiArray))
		self.moveCursor(QTextCursor.End)
		#QMessageBox.information(self, 'ASCII', ''.join(asciiArray))


class SerialWindow(QMainWindow):
	def __init__(self, logger = None, parent=None):
		super(SerialWindow, self).__init__(parent)
		self.setGeometry(300, 200, 1200, 650)
		self.baudrateList = ['115200', '9600', '38400']
		self.serialPort = 'COM1'
		self.baudrate = 115200
		self.ser = None
		self.portOpen = False
		self.asciiRead = False
		self.shortCuts = {}
		self.logger = logger

	def port_changed(self, index):
		self.open_serial_port()

	def show_text(self, text, colorHint):
		if text.strip() == '':
			return
		if self.timeEnable.isChecked():
			text = datetime.now().strftime('[%Y-%m-%d %H:%M:%S.%f] ') + text

		self.displayPanel.setFontPointSize(10)
		self.displayPanel.setFontWeight(QFont.Bold)
		
		if colorHint == 0:
			#green
			self.displayPanel.setTextColor(QColor('green'))
			self.displayPanel.append(text)
			self.displayPanel.setTextColor(QColor('grey'))
			self.displayPanel.append('.'*80)

		elif colorHint == 1:
			#black
			self.displayPanel.setTextColor(QColor('blue'))
			self.displayPanel.append(text)
		elif colorHint == 2:
			#red
			self.displayPanel.setTextColor(QColor('red'))
			self.displayPanel.append(text)
			self.displayPanel.setTextColor(QColor('grey'))
			self.displayPanel.append('.'*80)

		self.displayPanel.moveCursor(QTextCursor.End)

	def baud_changed(self, index):
		self.baudrate = self.baudrateList[index]

	def read_serial_port(self):
		while self.portOpen == True:
			dataToRead = self.ser.in_waiting
			if 0 == dataToRead:
				time.sleep(1)
			else:
				ret = self.ser.read(dataToRead)
				if self.asciiRead == True:
					self.show_text(ret.decode('utf-8'), 0)
				else:
					self.show_text(self.bytes_str(ret), 0)

		if None != self.ser:
			#close serial port
			self.ser.close()
			self.openButton.setText('OPEN')

	def open_serial_port(self):
		try:
			if self.portOpen == True:
				if self.ser:
					self.ser.close()
					self.ser = None

				if type(self.sender()) is QPushButton:
					self.openButton.setText('OPEN')
					self.portOpen = False
					return

			self.serialPort = self.ports[self.portSelect.currentIndex()].device
			self.ser = serial.Serial(port=self.serialPort, baudrate=self.baudrate, timeout=0)

			if self.ser.isOpen() == False:
				self.show_text('Open port failed', 2)
			else:
				self.portOpen = True
				self.openButton.setText('CLOSE')

				#create new thread for serial reading
				readThread = threading.Thread(target=self.read_serial_port)
				readThread.start()

		except StopIteration as iterError:
			print("Error: ", iterError)
		except Exception as e:
			print("Error: ", e)

	def hex_bytes(self, text):
		ret = []
		count = 0
		value = 0
		for index in range(0, len(text)):
			
			if text[index] != ' ' and text[index] != '\n':
				
				if count == 0:
					value = int(text[index], 16)
					count = 1
				
				elif count == 1:
					value <<= 4
					value |= int(text[index], 16)
					ret.append(value)
					value = 0
					count = 0

		return ret

	def bytes_str(self, intArray):

		retStr = ''
		for index in range(0, len(intArray)):
			retStr += str(hex(intArray[index])).lstrip('0x').zfill(2).upper()
			retStr += ' '
		return retStr

	def send_out(self):
		if self.portOpen == False or self.ser == None:
			self.show_text('Port closed', 2)

		else:
			writeText = self.sendBuffer.text()
			self.show_text(writeText.upper(), 1)

			if writeText.startswith(('at', 'aT', 'At', 'AT')):
				self.asciiRead = True
				writeText += '\r'
				self.ser.write(writeText.strip(' ').encode('utf-8'))
			else:
				self.asciiRead = False
				self.ser.write(self.hex_bytes(writeText.strip()))

	def clear_display_panel(self):
		self.displayPanel.clear()

	def send_out_shortcut(self):
		text = self.shortCuts.get(self.sender().text())

		if self.portOpen == False or self.ser == None:
			self.show_text('Port closed', 2)

		else:
			self.show_text(text.upper(), 1)

			if text.startswith(('at', 'aT', 'At', 'AT')):
				self.asciiRead = True
				text += '\r'
				self.ser.write(text.strip(' ').encode('utf-8'))
			else:
				self.asciiRead = False
				self.ser.write(self.hex_bytes(text.strip()))

	def set_shortcuts(self):
		config = configparser.ConfigParser()
		config.optionxform=str
		config.read(os.path.dirname(sys.executable) + '\serial.conf')

		for key in config['shortcuts']:
			button = QPushButton(key, self.table)
			self.table.insertRow(self.table.rowCount())
			self.table.setCellWidget(self.table.rowCount() - 1, 0, button)
					
			button.clicked.connect(self.send_out_shortcut)
			self.shortCuts[key] = config['shortcuts'][key]

	def check_serial_port(self):
		while self.serial_check_run:
			if self.ports != list_ports.comports():
				self.portSelect.clear()
				self.ports = list_ports.comports()
				try:
					#try find if current port missing
					index = 0
					found = False
					for device in self.ports:
						self.portSelect.addItem(device.description)
						if device.device == self.serialPort:
							found = True
							self.portSelect.setCurrentIndex(index)
						index = index + 1

					if found == False:
						self.portOpen = False
						self.portSelect.setCurrentIndex(0)
						self.show_text('Serial ports changed', 2)
					
				except Exception as e:
					self.portOpen = False
					#nothing need to do
					pass				

			time.sleep(2)

	def add_config_item(self):
		try:
			shutil.copy(os.path.dirname(sys.executable) + '\serial.conf', os.path.dirname(sys.executable) + '\serial.conf~')
			subprocess.call(['notepad.exe', os.path.dirname(sys.executable) + '\serial.conf~'])

			newShortCuts = {}
			index = 0
			config = configparser.ConfigParser()
			config.optionxform=str
			config.read(os.path.dirname(sys.executable) + '\serial.conf~')

			for key in config['shortcuts']:
				if index < self.table.rowCount():

					if key != self.table.cellWidget(index, 0).text():
						self.table.cellWidget(index, 0).setText(key)				
					else:
						#new item need to be added
						button = QPushButton(key, self.table)
						self.table.insertRow(index)
						self.table.setCellWidget(index, 0, button)
						button.clicked.connect(self.send_out_shortcut)

						index = index + 1
						newShortCuts[key] = config['shortcuts'][key]

			if index < self.table.rowCount():
				for i in range(index, self.table.rowCount()):
					self.table.removeRow(i)

			shutil.move(os.path.dirname(sys.executable) + '\serial.conf~', os.path.dirname(sys.executable) + '\serial.conf')
			self.shortCuts = newShortCuts.copy()

		except Exception as e:
			QMessageBox.critical(self, 'Error', str(e))

	def setup_window(self):
		window = QWidget()
		window.setWindowTitle('Serial Port Tool')
	
		windowLayout = QHBoxLayout()
		leftGroup = QGroupBox("Operation area")
		leftGroup.setFixedWidth(800)
		self.rightGroup = QGroupBox("Short cuts")

		windowLayout.addWidget(leftGroup)
		windowLayout.addWidget(self.rightGroup)
	
		leftGroupLayout = QHBoxLayout()
		inputGroup = QGroupBox()
		inputGroup.setFixedWidth(800)
	
		inputGroupLayout = QVBoxLayout()
	
		serialSetGroup = QGroupBox(parent = inputGroup)
		serialSetGroup.setFixedWidth(670)
		serialSetGroupLayout = QGridLayout()
		portLabel = QLabel('Port')
	
		portLabel.setAlignment(Qt.AlignLeft | Qt.AlignCenter)
		serialSetGroupLayout.addWidget(portLabel, 0, 1, 1, 1)
		self.portSelect = QComboBox()
		self.portSelect.setSizeAdjustPolicy(QComboBox.AdjustToContents)
	
		self.ports = list_ports.comports()
		for i in range(0, len(self.ports)):
			self.portSelect.addItem(self.ports[i].description)
	
		self.portSelect.currentIndexChanged.connect(self.port_changed)
		serialSetGroupLayout.addWidget(self.portSelect, 0, 2)
	
		baudLabel = QLabel('Baudrate')
		serialSetGroupLayout.addWidget(baudLabel, 0, 3)
		baudSelect = QComboBox()

		baudSelect.addItems(self.baudrateList)
		baudSelect.currentIndexChanged.connect(self.baud_changed)
		serialSetGroupLayout.addWidget(baudSelect, 0, 4)
	
		self.openButton = QPushButton('OPEN')
		serialSetGroupLayout.addWidget(self.openButton, 0, 5)
		self.openButton.clicked.connect(self.open_serial_port)
	
		serialSetGroup.setLayout(serialSetGroupLayout)
		inputGroupLayout.addWidget(serialSetGroup)
	
		self.displayPanel = MyTextEdit(parent = inputGroup)
		self.displayPanel.setFixedWidth(670)
		self.displayPanel.setReadOnly(True)
		inputGroupLayout.addWidget(self.displayPanel)
	
		self.sendBuffer = QLineEdit()
		self.sendBuffer.setFixedWidth(670)
		self.sendBuffer.returnPressed.connect(self.send_out)
		inputGroupLayout.addWidget(self.sendBuffer)
	
		inputGroup.setLayout(inputGroupLayout)
		leftGroupLayout.addWidget(inputGroup)
	
		inputBtnGroup = QGroupBox()
		inputBtnGroupLayout = QVBoxLayout()
		self.clearButton = QPushButton('Clear')
		inputBtnGroupLayout.addWidget(self.clearButton)
		self.timeEnable = QCheckBox('Show time')
		inputBtnGroupLayout.addWidget(self.timeEnable)
		self.clearButton.clicked.connect(self.clear_display_panel)
		self.sendButton = QPushButton('Send')
		inputBtnGroupLayout.addWidget(self.sendButton)
		self.sendButton.clicked.connect(self.send_out)

		addCfgButton = QPushButton('Add shotcuts')
		addCfgButton.clicked.connect(self.add_config_item)
		inputBtnGroupLayout.addWidget(addCfgButton)
	
		inputBtnGroup.setLayout(inputBtnGroupLayout)
		leftGroupLayout.addWidget(inputBtnGroup)
	
		leftGroup.setLayout(leftGroupLayout)
	
		self.rightGroupLayout = QVBoxLayout()
		self.table = QTableWidget()
		self.table.horizontalHeader().setVisible(False)
		self.table.horizontalHeader().setStretchLastSection(True)
		self.table.setColumnCount(1)
		self.table.setRowCount(0)
		self.rightGroupLayout.addWidget(self.table)
		self.set_shortcuts()
		self.rightGroup.setLayout(self.rightGroupLayout)
	
		window.setLayout(windowLayout)
		
		self.setCentralWidget(window)
		self.statusBar().showMessage('Report bug to itzyx@qq.com')
		
		comCheck = threading.Thread(target=self.check_serial_port)
		self.serial_check_run = True
		comCheck.start()

	def closeEvent(self, event):
		if self.portOpen == True and self.ser:
			self.portOpen = False
			self.ser.close()

		self.serial_check_run = False
		event.accept()

if __name__ == '__main__':
	app = QApplication(sys.argv)
	logging.config.fileConfig(fname=os.path.dirname(sys.executable) + '\serial.conf')
	logger = logging.getLogger('default')
	logger.info('start up')
	mainWindow = SerialWindow(logger)
	mainWindow.setup_window()
	mainWindow.show()
	logger.info('stop')
	sys.exit(app.exec_())
