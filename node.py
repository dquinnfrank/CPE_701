# A single node in the network
# Serves as the "main" for the project

import socket
import select
import sys
import os
import logging
import time

from general_utility import *
import UDP_socket
import link
import DNP
import route
import message

# A node in the network
# Reads all incoming packets and takes user input
class Node:

	# Starts the node
	# Needs the ID of this node and the configuration file for the network
	def __init__(self, node_id, topology_file, loss_chance = 0, corruption_chance = 0, select_timeout=.1, cleanup_timeout=.5):

		# The buffer size when getting data from the socket
		self.buffer_size = 4096

		# The time to wait for input from select before running other tasks
		self.select_timeout = select_timeout

		# Time to wait before running cleanup on services
		self.cleanup_timeout = cleanup_timeout

		# This list holds packets to be sent
		# Should only be sending to linked neighbors
		# (message, (ip, port))
		self.send_list = []

		# This dictionary holds the services, each number is similar to a port number
		self.services = {}

		# Save the node ID and the topology file
		self.node_id = node_id
		self.topology_file = topology_file

		# Get information about this node from the topology file
		(ip, port, connection1, connection2, mtu) = get_topology_from_file(self.topology_file, self.node_id)

		# Open a UDP socket with the info
		self.main_socket = UDP_socket.UDP_socket(ip, port, loss_chance, corruption_chance)

		# Create the DNP packet handler
		self.DNP = DNP.DNP(self.node_id, self.send_list)

		# Save the socket read and the user input for use with select
		self.inputs = [sys.stdin, self.main_socket.sock]

		# Create the standard services that run on every node
		self.create_standard_services()

		# Set the routing layer in DNP
		self.DNP.set_routing(self.services[2])

	# TODO: use @classmethod to make a constructor that loads from a file

	# Runs the node by accepting packets and user commands
	def run(self):

		self.quit = False

		# Time since cleanup was last run
		last_cleanup = time.time()

		# Show the menu
		self.show_menu()

		# Continue to run until quit
		while not self.quit:

			# Get input from select
			input_from, ignore, ignore = select.select(self.inputs, [], [], self.select_timeout)

			# Go through the inputs
			for input_item in input_from:

				# User input
				if input_item is sys.stdin:

					# Get the input
					user_input = input_item.readline().strip("\n ")

					# Separate the command from any contents
					out = user_input.split(" ", 1)
					if len(out) > 1:
						command = out[0]
						contents = out[1]
					else:
						command = out[0]
						contents = None

					# Deal with the command
					self.do_user_input(command, contents)

				# Socket input
				else:

					# Get the input string
					socket_input = input_item.recv(self.buffer_size)

					# TEMP echo to make sure it works
					#print "Socket input:\n" + socket_input

					# Use DNP to open the packet
					result = self.DNP.unpack(socket_input)

					# If the return is not None, forward the packet to the specified service
					if result is not None:

						service_id = int(result[0])

						# Get the service, fails if the service doesn't exist
						try:

							server = self.services[service_id]

						# That service doesn't exist
						except KeyError:

							logging.warning("Service does not exist: " + str(service_id) + " requested by: " + str(result[1]))

						# Have the service handle the packet
						else:

							try:
								server.serve(result)

							# Blissfully ignore problems
							except:

								logging.error("Unexpected error:" + str(sys.exc_info()[0]))

			# Send all messages waiting
			if len(self.send_list) > 0:

				self.send_waiting()

			# Do cleanup if enough time has passed
			if time.time() - last_cleanup > self.cleanup_timeout:

				# TEMP print to show working
				#print "Doing cleanup"
				pass

	# Creates the standard services at a node
	#
	# 1 : ping
	# A simple message that does not show to the screen
	#
	# 2 : routing
	# Used for informing nodes about routing changes
	#
	# 3 : establish connection
	# Used for creating dynamic ports
	#
	# 4 : message
	# A simple message that will display on the screen
	def create_standard_services(self):

		# Routing
		self.services[2] = route.Route(self.node_id, self.topology_file, self.DNP)

		# Save the common name for the routing
		self.router = self.services[2]

		# Messaging
		self.services[4] = message.Message(self.DNP, 4)

		# Common name for messaging
		self.console_message = self.services[4]

	# Sends all of the messages in send_list
	def send_waiting(self):

		# TEMP
		#print "Sending messages:"
		#print self.send_list
		logging.debug("Sending messages:\n" + str(self.send_list))

		# Send every message
		self.main_socket.send_all_garbled(self.send_list)

		# Reset the message list
		del self.send_list[:]

	# Handles user input
	def do_user_input(self, command, contents):

		print ""

		# Quit
		if command == "quit":

			print "Quiting program"

			self.quit = True

		# Show menu again
		elif command == "menu":

			self.show_menu()

		# Message another node
		elif command == "message":

			# Get the target and the message to send
			target_id, message = contents.split(" ", 1)

			self.console_message(target_id, message)

		# See the current routing table
		elif command == "routing_table":

			to_show = self.router.routing_table_string()

			print "Current routing table:"
			print to_show

		# Command not known
		else:

			print "Command not known: " + command
			print "Remember: 'menu' will show the list of commands"

		print ""

	# Shows the menu for user commands
	def show_menu(self):

		print ""
		print "-"*75
		print "Node: " + str(self.node_id)
		print "User commands: "
		print "'quit' to quit"
		print "'menu' to show this menu again"
		print "'message' [node id to send to] [what to send] to send a message to another node"
		print "'routing_table' to show the current routing table"
		print "-"*75
		print ""
