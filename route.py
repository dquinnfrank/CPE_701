# Routing
# This determines the next hop for a packet given the destination node
# Not part of the stack, this returns the link to send a packet over

import logging
import copy

from general_utility import *
#import link

class Route:

	# Initializes the dictionaries for routing and the objective for calculating shortest paths
	def __init__(self, node_id, topology_file, cost_function = "fewest_hops"):

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
		self.node_id_to_next_hop = {node_id : (node_id, 0)}

		# Load the file to get the network topology
		ip, port, connection1, connection2, mtu = get_topology_from_file(topology_file, node_id)

		# Go through the connections and get their info from the file
		for connection_id in (connection1, connection2):

			# Get info
			conn_ip, conn_port, ignore1, ignore2, conn_mtu = get_topology_from_file(topology_file, connection_id)

			# Add as next hop
			self.add_connection(connection_id, conn_ip, conn_port, conn_mtu)

			# Add to the routing table as single hops
			self.node_id_to_next_hop[connection_id] = (connection_id, self.cost_function(0))

		# Used temporarily when updating routing table
		# Do not use for routing
		# node_id : (connection_id, cost)
		self.unstable_route = copy.copy(self.node_id_to_next_hop)

		# Holds the basic link info, used for reseting unstable_route
		self.link_info = copy.copy(self.unstable_route)

	# Gets the next hop for a packet given the final target node id
	# Output is suitable for use with UDP_socket
	def get_next_hop(self, target_id):

		# Get the next hop for this target
		next_hop_id = self.node_id_to_next_hop[int(target_id)]

	# Adds a next hop link to this node
	def add_connection(self, connection_id, connection_ip, connection_port, connection_mtu):

		self.node_id_to_UDP[int(connection_id)] = (connection_ip, connection_port, connection_mtu)

	# Calculates cost based on number of hops
	# Basically just adds 1
	def fewest_hops(self, tail_cost):

		return tail_cost + 1

	# Updates the routing table based on the advertisement message
	# advertisement : (source_id, (can_reach_id, cost) ...)
	def update_routing(self, advertisement):

		# Unpack the advertisement
		source_id = advertisement[0]
		reach_info = advertisement[1:]

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

					self.unstable_route[target_id] = (source_id, ad_cost)

				# In case of ties, use the node with the lower id
				elif ad_cost == current_cost and source_id < current_next_hop:

					self.unstable_route[target_id] = (source_id, ad_cost)

	# Makes the updated routing table into the new rounting table
	# TODO: make this safer? Calling will wipe out the table if done at the wrong time
	def stablize(self):

		# Set the useable routing table to be the updated routing table
		self.node_id_to_next_hop = copy.copy(self.unstable_route)

		logging.info("Routing table updated: " + self.routing_table_string(" "))

		# Reset the unstable routing table
		self.unstable_route = copy.copy(self.link_info)

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
			entry_string = "Target--" + target_id + "--NextHop--" + next_hop + "--Cost--" + str(cost)

			# Add to list
			entry_list.append(entry_string)

		# Join all entries
		routing_table_string = sep.join(entry_list)

		return routing_table_string
