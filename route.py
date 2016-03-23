# Routing
# This determines the next hop for a packet given the destination node
# Not part of the stack, this returns the link to send a packet over

import logging
import copy

from general_utility import *
#import link

class Route:

	# Initializes the dictionaries for routing and the objective for calculating shortest paths
	def __init__(self, node_id, topology_file, DNP, cost_function = "fewest_hops"):

		# Holds the possible cost functions
		self.costs = {"fewest_hops" : self.fewest_hops}

		# Uses node names to get the destination IP, port, and MTU for use with UDP_socket
		# Should only hold info for nodes directly connected with this node
		# node_id : (ip, port, mtu)
		self.node_id_to_UDP = {}

		# Set the cost function
		self.cost_function = self.costs[cost_function]

		# Uses the routing protocol to find the next hop for a given node ID
		# Meaning of cost changes based on how best path is being determined
		# Cost to self is always 0
		# target_id : (next_hop_id, cost)
		self.node_id_to_next_hop = {int(node_id) : (int(node_id), 0)}

		# Load the file to get the network topology
		ip, port, connection1, connection2, mtu = get_topology_from_file(topology_file, node_id)

		# Go through the connections and get their info from the file
		for connection_id in (connection1, connection2):

			# Get info
			conn_ip, conn_port, ignore1, ignore2, conn_mtu = get_topology_from_file(topology_file, connection_id)

			# Add as next hop
			self.add_connection(connection_id, conn_ip, conn_port, conn_mtu)

			# Add to the routing table as single hops
			self.node_id_to_next_hop[int(connection_id)] = (int(connection_id), self.cost_function(0))

		# Used temporarily when updating routing table
		# Do not use for routing
		# node_id : (connection_id, cost)
		self.unstable_route = copy.copy(self.node_id_to_next_hop)

		# Holds the basic link info, used for reseting unstable_route
		self.link_info = copy.copy(self.unstable_route)

		self.stablize()

	# The entry point for packets handled by the routing service
	# Expects a packet as unpacked by DNP
	#
	# Advertisements have the form: target_id,cost;target_id,cost;...
	def serve(self, packet):

		# Get the readable contents of the package
		(dest_port, source_id, source_port, message) = packet

		# Break the message into the advertisement pairs
		pairs = message.split(";")

		# Break each pair into id and cost and add to the advertisement
		advertisement = []
		for item in pairs:

			advertisement.append(pairs.split(","))

		# Update the routing table
		self.update_routing(source_id, advertisement)

	# Returns the info needed for UDP_socket based on the target node
	def get_next_hop_sock(self, target_id):

		# Get the info to send to
		send_info = self.node_id_to_UDP[self.get_next_hop(target_id)]

		return send_info

	# Gets the next hop for a packet given the final target node id
	# returns the id of the neighbor
	def get_next_hop(self, target_id):

		# Get the next hop for this target, fails if the target cannot be reached
		try:

			next_hop_id = self.node_id_to_next_hop[int(target_id)][0]

		except KeyError:

			raise KeyError(str(target_id) + " is not reachable")

		# Check for an unreachable destination
		if next_hop_id == "UNREACHABLE":

			raise KeyError(str(target_id) + " is not reachable")

		return next_hop_id

	# Adds a next hop link to this node
	def add_connection(self, connection_id, connection_ip, connection_port, connection_mtu):

		self.node_id_to_UDP[int(connection_id)] = (connection_ip, connection_port, connection_mtu)

	# Calculates cost based on number of hops
	# Basically just adds 1
	def fewest_hops(self, tail_cost):

		return tail_cost + 1

	# Updates the routing table based on the advertisement message
	# advertisement : ((can_reach_id, cost), ...)
	def update_routing(self, source_id, advertisement):

		# Unpack the advertisement
		#source_id = advertisement[0]
		#reach_info = advertisement[1:]
		reach_info = advertisement

		# Go through each node / cost and check if it is better than what is currently stored in the table
		for (target_id, cost) in reach_info:

			# Get the cost of using this path
			ad_cost = self.cost_function(cost)

			# If this id is not in the list, add it with the updated cost
			if target_id not in self.unstable_route.keys():

				self.unstable_route[target_id] = (source_id, ad_cost)

			# id is in the routing table, update the entry if this new advertisement is better
			else:

				# Get the current info
				(current_next_hop, current_cost) = self.unstable_route[target_id]

				# Use the new cost if it is less than the current cost
				if ad_cost < current_cost:

					self.unstable_route[int(target_id)] = (int(source_id), ad_cost)

				# In case of ties, use the node with the lower id
				elif ad_cost == current_cost and source_id < current_next_hop:

					self.unstable_route[int(target_id)] = (int(source_id), ad_cost)

	# Makes the updated routing table into the new rounting table
	# TODO: make this safer? Calling will wipe out the table if done at the wrong time
	def stablize(self):

		# Set the useable routing table to be the updated routing table
		self.node_id_to_next_hop = copy.copy(self.unstable_route)

		logging.info("Routing table updated: " + self.routing_table_string(" "))

		# Reset the unstable routing table
		self.unstable_route = copy.copy(self.link_info)
	'''
	# Creates an advertisement message based on the current unstable routing table
	def make_advertisement_packet(self):

		# Go through the unstable table
		advertisement_message = ""
		for target_id in self.unstable_route.keys():

			# Add the id and the cost to the message
			advertisement_message += str(target_id) + "," + str(self.unstable_route[target_id][1]) + ";"

		# Send the packet to the neighbors
		for neighbor_id in self.node_id_to_UDP.keys():

			# Get the UDP info

			# Send the advertisement
			self.DNP.send(message, )
	'''
	# Returns the current routing table as a string
	# One entry is:
	# Target--node_id--NextHop--next_hop--Cost--cost
	# Multiple entries joined by sep
	def routing_table_string(self, sep="\n"):

		# Go through the current routing table and add each entry to the list
		entry_list = []
		for target_id in self.node_id_to_next_hop.keys():

			# Get the info for this target
			next_hop, cost = self.node_id_to_next_hop[target_id]

			# Make the string
			entry_string = "Target--" + str(target_id) + "--NextHop--" + str(next_hop) + "--Cost--" + str(cost)

			# Add to list
			entry_list.append(entry_string)

		# Join all entries
		routing_table_string = sep.join(entry_list)

		return routing_table_string
