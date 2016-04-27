# Service point. Acts as a listener

import logging
import time
import random

import RTP

from general_utility import *

class ServicePoint:

	# Creates a service point for accepting downloads
	def __init__(self, node_id, service_id, DNP, service_list, max_connections=3):

		self.node_id = node_id

		# This becomes the listen port
		self.service_id = service_id

		self.DNP = DNP

		# This is the list of services in the node
		self.service_list = service_list

		self.max_connections = 3

		# The connections being managed
		# service_id : RTP
		self.connections = {}

		# Targets that are connected to
		self.connected_to = []

		self.last_cleanup = time.time()

		# The connection used for sending
		self.send_connection = None

	# Makes new connections and handles existing ones
	def serve(self, packet):

		# Get the readable version of the contents
		(dest_port, source_id, source_port, message) = packet

		#print packet

		# If the target is requesting a connection
		if int(dest_port) == self.service_id:

			self.accept_connection(source_id, source_port, packet)

		else:

			# Use the connection to unpack
			self.connections[int(dest_port)].serve(packet)

	# Cleanup for all of the connections
	def cleanup(self):

		# Prevents multiple calls to cleanup in a short period
		if time.time() - self.last_cleanup < .1:

			return None

		for connection_id in self.connections.keys():

			# The connection, may throw errors if something has timedout
			try:

				self.connections[connection_id].cleanup()

			# Pipe is broken
			except RuntimeError:

				try:
					conn_to = self.connections[connection_id].target_port

				except AttributeError:
					conn_to = self.connections[connection_id].listen_port

				logging.warning("Connection broken: " + str(connection_id) + " " + str(conn_to))

				# Remove from the connections list and the service list
				self.remove_connection(connection_id)

		# Last time clean up was run
		self.last_cleanup = time.time()

	# Start a new connection
	def start_connection(self, target_node_id, connection_id=None, listen_port=10, window=5):

		# Fails if max connections is already reached
		if len(self.connections) >= self.max_connections:

			raise RuntimeError("Could not start connection, maximum connections reached")

		# If none, assign a random number not already being used
		if connection_id is None:
			rand_id = random.randint(20, 500)
			while (rand_id in self.service_list.keys()):

				rand_id = random.randint(20, 500)

			connection_id = rand_id

		# Fails if destination is not reachable
		try:
			self.connections[connection_id] = RTP.RTP(self.node_id, connection_id, self.DNP, target_node_id, self.connected_to, listen_port=listen_port, window=window)

		except KeyError:

			logging.warning("Destination is not reachable: " + str(target_node_id))

			return -1

		else:

			self.service_list[connection_id] = self

			self.send_connection = connection_id

			return connection_id

	# Accept a connection
	def accept_connection(self, target_id, target_port, packet, connection_id=None):

		# Fails if max connections is already reached
		if len(self.connections) >= self.max_connections:

			raise RuntimeError("Could not accept connection, maximum connections reached")

		# If none, assign a random number not already being used
		if connection_id is None:
			rand_id = random.randint(20, 500)
			while (rand_id in self.service_list.keys()):

				rand_id = random.randint(20, 500)

			connection_id = rand_id

		# Get the window size
		window = RTP.get_window(packet)

		self.connections[connection_id] = RTP.RTP(self.node_id, connection_id, self.DNP, target_id, self.connected_to, target_port=target_port, window=window)

		self.service_list[connection_id] = self

		return connection_id

	# Removes a connection
	# Throws error if connection does not exist
	def remove_connection(self, connection_id):

		del self.connections[connection_id]

		del self.service_list[connection_id]

	# Returns a string showing open connections
	def connection_string(self):

		if len(self.connected_to) == 0:

			return "No connections"

		conns = ''
		for conn in self.connected_to:

			conn_port = conn[0]

			conns += "NodeID: " + str(conn[1]) + " Port Number: " + str(conn[2]) + " Window: " + str(self.connections[conn_port].window) + "\n"

		return conns
