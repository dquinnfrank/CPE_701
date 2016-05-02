# Routing
# This determines the next hop for a packet given the destination node
# Not part of the stack, this returns the link to send a packet over

import logging
import copy
import time

from general_utility import *
#import link

class Route:

	# Initializes the dictionaries for routing and the objective for calculating shortest paths
	def __init__(self, node_id, topology_file, DNP, service_id = 2, cost_function = "fewest_hops", heartbeat_interval=.5, stablize_interval=2.0, replace_interval = .51):

		# Simple packet sender
		self.DNP = DNP

		self.service_id = service_id
		self.node_id = node_id

		# How often to ping neighbors
		self.heartbeat_interval = heartbeat_interval

		# How long to wait for updates
		self.stablize_interval = stablize_interval

		# How long to keep dead links out
		self.kill_replace = replace_interval

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
		self.ip, self.port, connection1, connection2, self.mtu = get_topology_from_file(topology_file, node_id)

		# Go through the connections and get their info from the file
		for connection_id in (connection1, connection2):

			# Get info
			conn_ip, conn_port, ignore1, ignore2, conn_mtu = get_topology_from_file(topology_file, connection_id)

			# Add as next hop
			self.add_connection(connection_id, conn_ip, conn_port, int(conn_mtu))

			# Add to the routing table as single hops
			self.node_id_to_next_hop[int(connection_id)] = (int(connection_id), self.cost_function(0))

		# Used temporarily when updating routing table
		# Do not use for routing
		# node_id : (connection_id, cost)
		#self.unstable_route = copy.copy(self.node_id_to_next_hop)
		self.unstable_route = {int(node_id) : (int(node_id), 0)}

		# Holds the basic link info, used for reseting unstable_route
		#self.link_info = copy.copy(self.unstable_route)
		#self.link_info = {int(node_id) : (int(node_id), 0)}
		self.link_info = copy.copy(self.node_id_to_next_hop)
		del self.link_info[self.node_id]

		# Marks if a link is not active
		self.active_links = {}
		for link_name in self.node_id_to_UDP.keys():
			self.active_links[link_name] = False

		# The max number of times to ping a node
		self.ping_max = 3

		# Tracks how many times a node has been pinged
		self.ping_count = {}
		for link_name in self.node_id_to_UDP.keys():
			self.ping_count[link_name] = 0

		# Tracks last time since neighbor responded to ping
		self.last_alive = {}
		for link_name in self.node_id_to_UDP.keys():
			self.last_alive[link_name] = 0

		# Last time since heartbeat was run
		self.last_beat = 0

		# Last time update happened
		self.last_update = 0

		# Recently killed links
		self.recently_killed = {}

		self.stablize()

	# The entry point for packets handled by the routing service
	# Expects a packet as unpacked by DNP
	#
	# Advertisements have the form: target_id,cost;target_id,cost;...
	def serve(self, packet):

		# Get the readable contents of the package
		(dest_port, source_id, source_port, message) = packet
		source_id = int(source_id)

		# Get the type of packet
		pkt_type, pkt_contents = message.split(";", 1)

		# Heartbeat
		if pkt_type == "1":
			logging.debug("Got heartbeat from: " + str(source_id))

			# Send response
			self.DNP.send("2;", source_id, self.service_id, self.service_id, TTL=1, link_only=True)

		# Ping response
		elif pkt_type == "2":

			logging.debug("Heartbeat response from: " + str(source_id))

			# Link just came back up
			if self.active_links[source_id] is False:

				logging.warning("Link alive: " + str(source_id))

				# Add the link back into the unstable routing table
				self.unstable_route[source_id] = (source_id, 1)
				self.last_update = time.time()

			# Set the neighbor as being alive
			self.last_alive[source_id] = time.time()
			self.active_links[source_id] = True

			# Reset the ping count for this neighbor
			self.ping_count[source_id] = 0

		# Update message
		elif pkt_type == "3":

			# Break the message into the advertisement pairs
			pairs = pkt_contents.split(";")

			# Break each pair into id and cost and add to the advertisement
			advertisement = []
			for item in pairs:
				if item is not "":
					advertisement.append(item.split(","))

			# Update the routing table
			self.update_routing(source_id, advertisement)

	# Checks to make sure that neighbors are alive
	# Triggers routing updates
	def cleanup(self):

		# Get the current time
		current_time = time.time()

		# Set any links that have been pinged more than 3 times to dead
		for link_name in self.ping_count.keys():
			link_name = int(link_name)

			# Link state before check
			previous_state = self.active_links[link_name]

			if self.ping_count[link_name] > 3:

				self.active_links[link_name] = False

				self.ping_count[link_name] = 0

				# Link was alive and is now dead
				if previous_state == True:

					logging.warning("Link dead: " + str(link_name))

					# If a link is dead, update the unstable table to not include dead links
					
					for target_id in self.unstable_route.keys():

						if self.unstable_route[target_id][0] == link_name:

							del self.unstable_route[target_id]
							self.last_update = time.time()

		# Ping after certain intervals
		if current_time - self.last_beat > self.heartbeat_interval:
		# TEMP override to always run
		#if True:

			# Ping all links
			for link_name in self.link_info.keys():

				self.DNP.send("1;", link_name, self.service_id, self.service_id, TTL=1, link_only=True)

				# Track number of pings
				self.ping_count[link_name] += 1

			# Send advertisement
			self.send_advertisement_packet()

		# Remove killed links and allow them back in
		for item in self.recently_killed.keys():
			if current_time - self.recently_killed[item] > self.kill_replace:

				del self.recently_killed[item]
				#print "back"

		# Stablize routing table
		if current_time - self.last_update > self.stablize_interval:
			#print "Stablize"
			self.stablize()

		# Set the last clean time to now
		self.last_beat = current_time

	# Returns the info needed for UDP_socket based on the target node
	def get_next_hop_sock(self, target_id, link_only=False):

		# Special case if this is the destination
		if int(target_id) == int(self.node_id):

			return (self.ip, self.port, self.mtu)

		# Get the info to send to
		send_info = self.node_id_to_UDP[self.get_next_hop(target_id, link_only=link_only)][:2]

		return send_info

	# Gets the next hop for a packet given the final target node id
	# returns the id of the neighbor
	def get_next_hop(self, target_id, link_only=False):

		# Special case if the target is this node
		if int(target_id) == int(self.node_id):

			return target_id

		# If link_only is true, consider only links of this node and ignore down links
		if link_only:

			return target_id

		# Normal routing
		else:

			# Get the next hop for this target, fails if the target cannot be reached
			try:

				next_hop_id = self.node_id_to_next_hop[int(target_id)][0]

			except KeyError:

				raise KeyError(str(target_id) + " is not reachable")

			# Check for an unreachable destination
			if next_hop_id == "UNREACHABLE":

				raise KeyError(str(target_id) + " is not reachable")

			return next_hop_id

	# Returns the id of the neighbor to send to and the mtu of the link
	# link_only True means that only links of this node will be considered, down or not
	def get_next_hop_info(self, target_id, link_only=False):

		next_hop_id = self.get_next_hop(target_id, link_only=link_only)

		link_mtu = self.get_link_mtu(next_hop_id)

		return next_hop_id, link_mtu

	# Gets the mtu for a link
	def get_link_mtu(self, target_id):

		# Fails if this node is not linked
		try:

			# Special case for connecting to this node
			if int(target_id) == int(self.node_id):

				link_mtu = 10000

			else:

				link_mtu = self.node_id_to_UDP[target_id][2]

		# Not linked
		except KeyError:

			raise KeyError("Not linked to node: " + str(target_id))

		else:

			return link_mtu

	# Adds a next hop link to this node
	def add_connection(self, connection_id, connection_ip, connection_port, connection_mtu):

		self.node_id_to_UDP[int(connection_id)] = (connection_ip, int(connection_port), int(connection_mtu))

	# Calculates cost based on number of hops
	# Basically just adds 1
	def fewest_hops(self, tail_cost):

		return int(tail_cost) + 1

	# Updates the routing table based on the advertisement message
	# advertisement : ((can_reach_id, cost), ...)
	def update_routing(self, source_id, advertisement):

		# Tracks if any updates were made
		updates_made = False

		# Unpack the advertisement
		#source_id = advertisement[0]
		#reach_info = advertisement[1:]
		reach_info = advertisement

		source_id = int(source_id)

		# Ignore phantom updates
		if not self.active_links[source_id]:

			return None

		# Go through each node in the current table
		# Any node in the table that uses that link, but is not in the advertisement indicates a dead link
		#print "dead check"
		for table_id in self.unstable_route.keys():

			table_id = int(table_id)
			#print self.unstable_route
			#print self.unstable_route[table_id], " ", source_id, " ", table_id, " ", reach_info
			#print int(self.unstable_route[table_id][0]) == source_id, " ", int(table_id) not in [int(r[0]) for r in reach_info]
			if int(self.unstable_route[table_id][0]) == source_id and int(table_id) not in [int(r[0]) for r in reach_info] and table_id != int(self.node_id):

				updates_made = True
				#print "deaded: ", table_id
				self.recently_killed[table_id] = time.time()

				# Remove the entry
				del self.unstable_route[table_id]

		# Go through each node / cost and check if it is better than what is currently stored in the table
		for (target_id, cost) in reach_info:

			target_id = int(target_id)

			# Get the cost of using this path
			ad_cost = self.cost_function(cost)


			# If this id is in the recently killed list, ignore it
			if target_id in self.recently_killed.keys():

				pass

			# If this id is not in the list, add it with the updated cost
			elif target_id not in self.unstable_route.keys():

				updates_made = True
				#print "new"

				self.unstable_route[target_id] = (source_id, ad_cost)

			# id is in the routing table, update the entry if this new advertisement is better
			else:

				# Get the current info
				(current_next_hop, current_cost) = self.unstable_route[target_id]

				# Use the new cost if it is less than the current cost
				if ad_cost < current_cost:

					updates_made = True
					#print "better"

					self.unstable_route[int(target_id)] = (int(source_id), ad_cost)

				# In case of ties, use the node with the lower id
				elif ad_cost == current_cost and source_id < current_next_hop:

					updates_made = True
					#print "tie"

					self.unstable_route[int(target_id)] = (int(source_id), ad_cost)

		# If any updates were made, set the update time
		if updates_made:

			self.last_update = time.time()

	# Resets unstable route based on the active links
	def reset_unstable(self):

		# Cost to self is always 0
		self.unstable_route = {int(self.node_id): (self.node_id, 0)}

	# Makes the updated routing table into the new rounting table
	# TODO: make this safer? Calling will wipe out the table if done at the wrong time
	def stablize(self):

		# Set the useable routing table to be the updated routing table
		self.node_id_to_next_hop = copy.copy(self.unstable_route)

		logging.debug("Routing table updated: " + self.routing_table_string(" "))

		# Reset the unstable routing table
		#self.unstable_route = copy.copy(self.link_info)
		#self.reset_unstable()

	# Sends an advertisement message based on the current unstable routing table
	def send_advertisement_packet(self):

		# Get the advertisement
		advertisement_message = self.make_advertisement_message()

		# Send the packet to the neighbors
		for neighbor_id in self.node_id_to_UDP.keys():

			# Send the advertisement
			self.DNP.send(advertisement_message, neighbor_id, self.service_id, self.service_id, TTL=1, link_only=True)

	# Makes an advertisement message
	def make_advertisement_message(self):

		# Go through the unstable table
		# The type of the message is first, 2 is an advertisement
		advertisement_message = "3;"
		for target_id in self.unstable_route.keys():

			# Add the id and the cost to the message
			advertisement_message += str(target_id) + "," + str(self.unstable_route[target_id][1]) + ";"

		return advertisement_message

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
