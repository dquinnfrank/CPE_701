# Message
# Sends and receives messages between users that are displayed onto the console
# Uses unreliable transport

import sys
import logging

from general_utility import *

class Message:

	# Initializes
	def __init__(self, DNP, service_id):

		self.DNP = DNP

		self.service_id = int(service_id)

	# Call will send a message
	def __call__(self, target_id, message):

		self.send(target_id, message)

	# Sends a message to the specified node
	def send(self, target_id, message):

		# Use DNP send, might fail
		try:
			self.DNP.send(message, target_id, self.service_id, self.service_id)

		except KeyError:

			print "Destination is not reachable: " + str(target_id)

		# Ignore other problems
		except:

			logging.error("Unexpected error:" + str(sys.exc_info()[0]))

	# Gets a message and shows it on the screen
	def serve(self, packet):

		# Readable version
		(dest_port, source_id, source_port, message) = packet

		# Show the message
		print ""
		print "Message from: " + str(source_id)
		print message
		print ""

