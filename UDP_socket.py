# This manages a UDP port
# Can be configured to send garbled messages to emulate packet loss / corruption

import string
import socket
import random
import logging

class UDP_socket:

	# Class members
	#
	# sock
	# The socket that was created. Can be read from using select
	# DO NOT SEND MESSAGES DIRECTLY THROUGH THIS
	# use send_garbled instead

	# Initializer
	# Sets socket values and garbling parameters
	#
	# ip_address : string
	# The IP of this host
	#	
	# port : int
	# The port number that this socket will bind to
	#
	# Garbling parameters. These will set the default levels for this socket
	#
	# loss_threshold : int
	# The chance from 0 - 100 that a packet will be entirely lost
	# Higher values mean more losses
	#
	# corruption_threshold : int
	# The chance from 0 - 100 that a packet, if not entirely lost, will be sent with errors
	# Higher values mean a higher chance for corruption
	def __init__(self, ip_address, port, loss_threshold = 0, corruption_threshold = 0):

		# Save the socket info
		self.ip_address = ip_address
		self.port = port

		# Save the garbling parameters
		self.current_loss_threshold = None
		self.current_corruption_threshold = None
		self.default_loss_threshold = loss_threshold
		self.default_corruption_threshold = corruption_threshold

		# Set the garbling parameters
		self.set_garble_parameters("DEFAULT", "DEFAULT")

		# Create and bind the UDP socket
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

		# Bind the socket
		self.sock.bind((self.ip_address, self.port))

		logging.warning("Bound socket to: " + str((self.ip_address, self.port)))

	# Releases the socket once this class is destroyed
	def __del__(self):

		self.sock.close()

		logging.warning("Closed socket: " + str((self.ip_address, self.port)))

	# Sends a message. Affected by current garbling parameters
	#
	# message
	# The data to send
	#
	# send_info : (destination_ip, destination_port)
	# The ip and port to send to
	def send_garbled(self, message, send_info):

		# Use the garble parameters to determine the fate of the message

		# Loss, failure means no sending
		if random.randint(1, 100) <= self.current_loss_threshold:

			logging.info("Packet loss sending to: " + str(send_info))
			logging.debug("Message contents: " + message)

			return

		# Corruption, failure means that the message will be randomly altered
		if random.randint(1, 100) <= self.current_corruption_threshold:

			logging.info("Packet corruption sending to: " + str(send_info))
			logging.debug("Message contents: " + message)

			message = ''.join(i if random.randint(0, 1) else random.choice(string.letters) for i in message)

		# Send the message
		self.sock.sendto(message, send_info)

		logging.info("Packet sent to: " + str(send_info))
		logging.debug("Message contents: " + message)

	# Sends a list of messages to the same address. Uses send_garbled
	def send_all_garbled(self, message_list, send_info):

		# Call send_garbled for each message
		for message in message_list:

			self.send_garbled(message, send_info)

	# Sets the garbling parameters of this socket
	# Throws execptions for invalid input
	#
	# loss_threshold : int
	# The chance from 0 - 100 that a packet will be entirely lost
	# Higher values mean more losses
	#
	# corruption_threshold : int
	# The chance from 0 - 100 that a packet, if not entirely lost, will be sent with errors
	# Higher values mean a higher chance for corruption
	#
	# Both of these values can be sent as strings, in which case the following will occur
	# SAME : current value will not be changed
	# DEFAULT : value set during class initialization will be used
	# NEVER : 0, no loss or corruption
	def set_garble_parameters(self, loss_threshold = "SAME", corruption_threshold = "SAME"):

		# Set based on any strings
		if isinstance(loss_threshold, basestring):

			# Don't change anything
			if loss_threshold == "SAME":

				set_loss_threshold_to = self.current_loss_threshold

			# Reset to original value
			elif loss_threshold == "DEFAULT":

				set_loss_threshold_to = self.default_loss_threshold

			# Set to 0 so that packets will never be lost
			elif loss_threshold == "NEVER":

				set_loss_threshold_to = 0

		# Treat this as a number
		else:

			set_loss_threshold_to = loss_threshold

		# Set based on any strings
		if isinstance(corruption_threshold, basestring):

			# Don't change anything
			if corruption_threshold == "SAME":

				set_corruption_threshold_to = self.current_corruption_threshold

			# Reset to original value
			elif corruption_threshold == "DEFAULT":

				set_corruption_threshold_to = self.default_corruption_threshold

			# Set to 0 so that packets will never be lost
			elif corruption_threshold == "NEVER":

				set_corruption_threshold_to = 0

		# Treat this as a number
		else:

			set_corruption_threshold_to = corruption_threshold

		# Check to make sure that both values are valid
		if not (0 <= set_loss_threshold_to <= 100):
		# Not valid

			raise ValueError("Loss threshold invalid: " + str(set_loss_threshold_to))

		if not (0 <= set_corruption_threshold_to <= 100):
		# Not valid

			raise ValueError("Corruption threshold invalid: " + str(set_corruption_threshold_to))

		# Set the garbling values
		self.current_loss_threshold = set_loss_threshold_to
		self.current_corruption_threshold = set_corruption_threshold_to

		logging.warning("Garble parameters set to: loss: " + str(self.current_loss_threshold) + " corruption: " + str(self.current_corruption_threshold))
