# A single node in the network
# Serves as the "main" for the project

import socket
import select
import sys
import os
import logging
import time
import random
from itertools import ifilterfalse
import argparse

from general_utility import *
import UDP_socket
import link
import DNP
import RTP
import route
import message
import service_point

# A node in the network
# Reads all incoming packets and takes user input
class Node:

	# Starts the node
	# Needs the ID of this node and the configuration file for the network
	def __init__(self, node_id, topology_file, loss_chance = 0, corruption_chance = 0, select_timeout=.01, cleanup_timeout=.5, logger_level="WARNING", logger_file_handle=None):

		# Set the logger file, if sent
		if logger_file_handle is not None:

			# Add the node id and .log to the handle
			log_file_name = logger_file_handle + "_" + str(node_id) + ".log"

			print "Saving log file to: " + log_file_name

			logging.basicConfig(level=logger_level, filename = log_file_name, filemode='a')

		else:

			logging.basicConfig(level=logger_level)

		logging.warning("Starting node: " + str(node_id))

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

		# This holds a list of ids that are service points
		self.service_points = []

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

		# Neighbor to link info
		# ID : (ip,port,mtu)
		self.link_info = {}
		self.info_to_id = {}
		for node_id in (int(connection1), int(connection2)):

			(ip, port) = self.router.get_next_hop_sock(node_id, link_only=True)

			mtu = self.router.get_link_mtu(node_id)

			#self.link_info[node_id] = self.router.get_next_hop_info(node_id, link_only=True)
			self.link_info[node_id] = (ip, port, mtu)
			self.info_to_id[(ip, port)] = node_id

		# Tracks downed links
		# Contains ids
		self.link_down = []

		# Tracks the ids of dynamic connections
		self.dyn_connections = []

	# TODO: use @classmethod to make a constructor that loads from a file

	# Destructor
	def __del__(self):

		logging.shutdown()

	# Runs the node by accepting packets and user commands
	# This is a blacking command, never stops until user quits
	def run(self):

		self.quit = False

		# Burn all queued packets
		start = time.time()
		burn_time = 1.0
		while time.time() - start < burn_time:

			input_from, ignore, ignore = select.select(self.inputs, [], [], .01)

			for input_item in input_from:
				if input_item is not sys.stdin:

					socket_input = input_item.recv(self.buffer_size)

		# Show the menu
		self.show_menu()

		# Time since cleanup was last run
		last_cleanup = time.time()

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

					#if not result:
					#	print "nothing"
					#elif result[2] != 2 and result[2] != 3:
					#	print "node ", result

					# Ignore heartbeats
					if result and result[2] != 2:
						logging.info("Got packet: " + str(result[:-1]))
						logging.debug("Contents: " + str(result[-1]))

					# If the return is not None, forward the packet to the specified service
					if result is not None:

						service_id = int(result[0])

						# Get the service, fails if the service doesn't exist
						try:

							server = self.services[service_id]

						# That service doesn't exist
						except KeyError:

							logging.info("Service does not exist: " + str(service_id) + " requested by: " + str(result[1]))

						# Have the service handle the packet
						else:

							try:
								server.serve(result)

							# Blissfully ignore problems
							except Exception, e:

								logging.error("Unexpected error:" + str(sys.exc_info()[0]))
								#print e

							# Don't ignore
							#except:

								#raise

			# Send all messages waiting
			if len(self.send_list) > 0:

				self.send_waiting()

			# Do cleanup if enough time has passed
			if time.time() - last_cleanup > self.cleanup_timeout:

				# Reset cleanup time
				last_cleanup = time.time()

				# TEMP print to show working
				#print "Doing cleanup"
				for service in self.services.values():

					# May not have any cleanup
					try:

						service.cleanup()

					# Doesn't have cleanup, just ignore
					#except AttributeError:

						#pass
					except:
						raise

				# Do cleanup on DNP
				self.DNP.cleanup()

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

		# Remove messages heading for a down link or bigger than the allowable MTU
		#for item in self.send_list:

			# Get the message
			#content = item[0]
			#(dest_ip, dest_port) = item[1]

			# Check the neighbor
			#neighbor_id = self.info_to_id[(dest_ip, dest_port)]

			#if 

		def determine(item):

			try:			
				neighbor_id = self.info_to_id[item[1]]

			except KeyError:
				#print self.info_to_id
				#print item
				return False

			(ip, port, mtu) = self.link_info[neighbor_id]
			#print neighbor_id, " ", mtu, " ", len(item[0])

			#if not (neighbor_id not in self.link_down and len(item[0]) <= mtu):
				#print "Too big: ", item

			return not (neighbor_id not in self.link_down and len(item[0]) <= mtu)

		self.send_list[:] = list(ifilterfalse(determine, self.send_list))

		#print "To send: ", len(self.send_list)

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

		# Set the values for the garbler
		elif command == "setGarble":

			if not contents or contents.split() < 2:

				print "Need loss, corruption"

			else:

				(loss, corruption) = [int(x) for x in contents.split()]

				# Fails for invalid values
				try:

					self.main_socket.set_garble_parameters(loss, corruption)

				except ValueError:

					print "Values not valid"

		# Down a link
		elif command == "downLink":

			if not contents:

				print "Need neighbor id"

			else:

				contents = int(contents)

				# Add to the down list
				if contents not in self.link_info.keys():

					print "Not a neighbor"

				elif contents in self.link_down:

					print "Link is already down"

				else:

					logging.warning("Link downed: " + str(contents))

					self.link_down.append(contents)

		# Bring link back up
		elif command == "upLink":

			if not contents:

				print "Need neighbor id"

			else:

				contents = int(contents)

				# Remove from downlist
				if contents not in self.link_info.keys():

					print "Not a neighbor"

				elif contents not in self.link_down:

					print "Link not down"

				else:

					logging.warning("Link reactivated: " + str(contents))

					self.link_down.remove(contents)
					if self.link_down == None:
						self.link_down = []

		# Message another node
		elif command == "message":

			# Get the target and the message to send
			target_id, message = contents.split(" ", 1)

			self.console_message(target_id, message)

		# See the current routing table
		elif command == "routing":

			to_show = self.router.routing_table_string()

			print "Current routing table:"
			print to_show

		# Start a download service
		elif command == "startService":

			# No number sent
			if not contents:

				print "Need max connections"

			else:
				#(service_id, max_connections) = contents.split()
				#service_id = int(service_id)
				#max_connections = int(service_id)
				max_connections = int(contents)

				#service_id = random.randint(10,19)

				rand_id = random.randint(20, 500)
				while (rand_id in self.services.keys()):

					rand_id = random.randint(20, 500)

				service_id = rand_id

				self.services[service_id] = service_point.ServicePoint(self.node_id, service_id, self.DNP, self.services, max_connections=max_connections)

				self.service_points.append(service_id)

				print "Service created: ", service_id
				#logging.info("Service created: " + str(service_id))

		# Connect to another node
		elif command == "connectTo":

			if not contents or len(contents.split()) < 3:

				print "Need target_id, target_port, window"

			else:

				try:

					(target_id, target_listen, window) = [int(item) for item in contents.split()]

				except ValueError:

					print "Incorrect input"

				else:

					max_connections = 1

					rand_id = random.randint(20, 500)
					while (rand_id in self.services.keys()):

						rand_id = random.randint(20, 500)

					service_id = rand_id

					service_temp = service_point.ServicePoint(self.node_id, service_id, self.DNP, self.services, max_connections=max_connections)

					conn_id = service_temp.start_connection(target_id, listen_port=target_listen, window=window)

					# Connection fails, error codes are < 0
					if conn_id < 0:

						service_temp = None

						if conn_id == -1:

							print "Connection failed, destination is not reachable"

						else:

							print "Connection failed"

					# Service complete
					else:

						self.services[service_id] = service_temp

						self.service_points.append(service_id)

						#print "Connection id: " + str(conn_id)
						print "Connection id: " + str(service_id)

		# Asks for a fire
		elif command == "download":

			if not contents or len(contents.split()) < 2:

				print "Need connectionID, file name"

			else:

				(connection_id, file_name) = contents.split()
				connection_id = int(connection_id)

				if connection_id not in self.services.keys():

					print "No connection with that id"

				else:

					self.services[connection_id].file_request(file_name)

		# Show the ids of active services
		elif command == "services":

			print "Service points:"
			for item in self.service_points:
				print item

		# Show the open connections on a service
		elif command == "connections":

			if not contents:
				print "Need service id"

			else:

				service_id = int(contents)

				if service_id in self.service_points:

					print self.services[service_id].connection_string()

				else:

					print "No service id with that number"

		# Show link status
		elif command == "links":

			for item in self.link_info.keys():

				# Get info
				ip, port, mtu = self.link_info[item]

				# Get MTU
				#mtu = self.

				print "Link to: ", item, " IP: ", ip, " Port: ", port, " MTU: ", mtu, " Active: ", item not in self.link_down
				#print info, " ", mtu , " ", item not in self.link_down

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
		print "'setGarble' [loss] [corruption] sets the garbler"
		print "'downLink' [neighbor id] deactivate this link"
		print "'upLink' [neighbor id] reactivate this link"
		print "'message' [node id to send to] [what to send] to send a message to another node"
		print "'routing' to show the current routing table"
		print "'services' to show active service points"
		print "'links' to show link status"
		print "'connections' [service id] show open connections on service"
		print "'startService' [max_connections] to start a download service"
		print "'connectTo' [target id] [target service] [window] connect to target node at service"
		print "'download' [connection id] [file name] gets the file though the connection"
		print "-"*75
		print ""

# If this is run as main, get options and start the node
if __name__ == "__main__":

	parser = argparse.ArgumentParser(description="Runs a node for the CPE 701 semester project")

	parser.add_argument("node_id", type=int, help="The ID number of the node to run")

	parser.add_argument("topology_file", help="The name of the network topology file. Send path and file name.")

	parser.add_argument("-l", "--loss" , dest="loss_chance", type=int, default=5, help="Sets the initial loss parameter in the garbler")

	parser.add_argument("-c", "--corruption", dest="corruption_chance", type=int, default=5, help="Sets the initial corruption parameter in the garbler")

	parser.add_argument("-f", "--loggerFile", dest="log_file", default=None, help="The name, including path, to save the log file to. Prevents many messages from printing to the screen")

	parser.add_argument("-v", "--loggerLevel", dest="log_level", default="WARNING", help="The level the logger operates on. ERROR, WARNING, INFO, DEBUG")

	# Get the arguments and unpack them
	args = parser.parse_args()

	# Create the node
	the_node = Node(args.node_id, args.topology_file, loss_chance = args.loss_chance, corruption_chance = args.corruption_chance, logger_level=args.log_level, logger_file_handle=args.log_file )

	# Run the node
	the_node.run()
