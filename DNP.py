# The basic packet handler
# This is the most fundamental layer since it provides enough info to properly direct a packet
# Handles most of the header info for end to end best effort service

import logging
import time

from general_utility import *
import link

class DNP:

	# Configures DNP protocol
	# buffer_timeout defines how long a fragmented message will be kept without an update before being dropped
	def __init__(self, node_id, send_list, buffer_timeout = .5, upper_layer = None):

		self.node_id = node_id

		# This holds a list of packets to be sent by the main node
		self.send_list = send_list

		# Holds information about next hops and link mtus
		# Placeholder, needs to be set later before using the class
		self.routing_layer = None

		self.buffer_timeout = buffer_timeout

		# Save the upper layer if there is one
		self.upper_layer = upper_layer

		# A number that is used to create packet ids
		self.packet_counter = 0

		# Holds fragmented messages
		# packet_key : ledger_dic
		# ledger_dic = [last_timestamp : last update time, total_size : expected packet size, data_buffer : list of current data chunks, byte_offsets : the corresponding offset of each chunk]
		self.message_buffer = {}

		# The link layer that will handle lower level communication
		self.lower_layer = link.Link(self)

	# Sets the routing info to be used for forwarding packets
	def set_routing(self, routing_layer):

		self.routing_layer = routing_layer

	# Sends a packet, uses pack to create the packet / fragments
	# Does not handle errors, such as an unreachable destination
	def send(self, message, destination_id, destination_port, source_port, link_mtu, TTL = None):

		# Get the packet ready for sending
		fragments = self.pack(message, destination_id, destination_port, source_port, link_mtu, TTL)

		# Get the send info from the routing table, fails if desintation not reachable
		send_info = self.routing_layer.get_next_hop_sock(destination_id)

		# Place each fragment into the send buffer
		for item in fragments:

			self.send_list.append((item, send_info))

	# Creates a best effort service packet
	# Returns a list of strings with the packet header and content
	# Each item in the list is a fragment of the packet, commonly there will only be one
	# TODO: take out mtu and get it from the route layer
	def pack(self, message, destination_id, destination_port, source_port, link_mtu, TTL = None):

		# Holds all of the fragments to send
		message_fragments = []

		# Encode the message as a standard format to ensure bytes are properly counted
		message = message.encode("utf8")

		# Save the total size of the message
		message_size = len(message)

		# Max size of a message body is based off of the link_mtu
		max_size = link_mtu - self.header_total()

		logging.info("Message sending to: " + str(destination_id))

		# If the message (and header) is larger than the mtu, it will need to be fragmented
		# Fragmentation will continue as long as needed
		message_remaining = message # Holds remaining message chunks
		offset_counter = 0 # Tracks the byte offset
		while len(message_remaining) > max_size:

			# Take a chunk of the message off and make a packet out of it
			message_chunk = message_remaining[:max_size]

			# Pack and add to the message list, will fail if TTL expires
			try:

				to_send = self.single_pack(message_chunk, destination_id, destination_port, source_port, TTL = TTL, offset = offset_counter, total_size = message_size)

			# TTL has expired, don't deal with it here for now
			except RuntimeError:

				# TODO: configure this to pass the error along if desired
				raise

			else:

				message_fragments.append(to_send)

				# Remove the packed message
				message_remaining = message_remaining[max_size:]

			# Set the byte offset by incrementing by the size of this fragment
			offset_counter += len(message_chunk)

		# Get the remainder of the message
		if len(message_remaining) > 0:

			# TTL catch
			try:

				to_send = self.single_pack(message_remaining, destination_id, destination_port, source_port, TTL = TTL, offset = offset_counter, total_size = message_size)

			# TTL expired
			except RuntimeError:

				raise

			else:
				message_fragments.append(to_send)

		# Incrment count
		offset_counter += 1

		return message_fragments

	# Makes a single packet, size must be less than the mtu
	def single_pack(self, message, destination_id, destination_port, source_port, TTL = None, offset = 0, total_size = None, increment = False):

		# If total is None, use the size of the message as the total
		if total_size is None:

			total_size = len(message)

		# Get the binary header for the DNP portion of the message
		DNP_header = pack_string([destination_id, self.packet_counter, offset, total_size, destination_port, self.node_id, source_port])

		# Concatinate with the body to make the DNP portion of the packet
		DNP_partial_packet = DNP_header + message

		# Finish the packet by adding the link layer info
		whole_packet = self.lower_layer.pack(DNP_partial_packet, TTL=TTL)

		# Increment the overall packet counter to keep IDs unique, if requested
		if increment:
			self.packet_counter += 1

		return whole_packet

	# Unpacks the given packet, return depends on the packet
	#
	# If the packet is not destined for this node, the packet will be forwarded and return will be None
	#
	# If this is a fragment, it will be placed in the buffer.
	# If all fragments are collected, the packet info and body will be returned
	# If there are more fragments, the return will be None
	def unpack(self, packet):

		# Unpack the packet, might fail
		try:

			unpacked = self.single_unpack(packet)

		# Just ignore corrupted packets
		except RuntimeError:

			return None

		# More readable form of the packet contents
		(TTL, dest_id, pkt_id, offset, total_size, dest_port, source_id, source_port, message) = unpacked

		# If this packet is not destined for this node, forward it
		if dest_id != self.node_id:

			logging.info("Got packet for another destination: " + str(dest_id))

			if self.routing_layer is not None:

				# TODO: get routing and forward packet
				pass

			return None

		# The common case is that the packet is not fragmented, immediately return
		if len(message) == total_size:

			return (dest_port, source_id, source_port, message)

		# This is a fragment
		else:

			# Place into buffer
			response = self.defragment(unpacked)

			if response is not None:

				return (dest_port, source_id, source_port, response)

			else:

				return None

	# Unpacks a single DNP packet
	# Returns all header info for this layer and TTL from the lower layer
	def single_unpack(self, packet):

		# Dummy to keep intenting happy while try is commented out
		if True:
		# Get the link info
		# Will fail if packet is corrupted
		#try:

			TTL, DNP_packet = self.lower_layer.unpack(packet)

		# Currently, do nothing about corrupt packets
		#except RuntimeError as r_error:

			#raise

		# Get the DNP info
		#else:

			# Separate the header from the body
			header = DNP_packet[:self.header_size()]
			body = DNP_packet[self.header_size():]

			# Get the header info
			DNP_header_info = unpack_string(header)

			# Return all info and the body
			return TTL + DNP_header_info + (body,)

	# Reassembles packet fragments
	# returns None if packet is not complete
	# returns the assembled message if complete
	def defragment(self, packet):

		# Get the readable form of the contents
		(TTL, dest_id, pkt_id, offset, total_size, dest_port, source_id, source_port, message) = packet

		# Get the key for this packet
		packet_key = self.buffer_key(dest_port, source_id, source_port, pkt_id)

		# Get the buffer if it is already in the ledger
		try:

			packet_buffer = self.message_buffer[packet_key]

		# This is a new packet
		except KeyError:

			# Add to the buffer
			packet_buffer = self.ledger_entry(packet)

		# Update the buffer with the new packet chunk
		self.ledger_update(packet_buffer, message, offset)

		# Attempt to combine the packet
		fused = self.ledger_combine(packet_buffer)

		# If fused contains data, the entry can be removed from the ledger
		if fused is not None:

			del self.message_buffer[packet_key]

		# Return the combined packet, will be None if not all fragements are present
		return fused

	# Attempts to combine the given packet buffer
	# Returns None if not all fragments are present
	# Returns all data if all fragments are present
	def ledger_combine(self, packet_buffer):

		# Combine all data
		combined_data = "".join(packet_buffer["data_buffer"])

		# Packet is complete if size of data is equal to the total_size
		if len(combined_data) == packet_buffer["total_size"]:

			# Send back all data
			return combined_data

		# Not complete
		else:

			return None

	# Updates the given ledger entry with the sent data and offset
	def ledger_update(self, packet_buffer, data, offset):

		# TODO: fix duplicates and non aligned repeats?
		# This might not even be an issue

		# Set the new time stamp
		packet_buffer["last_timestamp"] = time.time()

		# Add the offset
		packet_buffer["byte_offsets"].append(offset)

		# Sort and get the position of the new entry in order to know where the data needs to go
		packet_buffer["byte_offsets"].sort()
		chunk_index = packet_buffer["byte_offsets"].index(offset)

		# Insert the data into the correct location
		packet_buffer["data_buffer"].insert(chunk_index, data)

	# Creates an entry in the buffer ledger
	def ledger_entry(self, packet):

		# Get the readable form of the contents
		(TTL, dest_id, pkt_id, offset, total_size, dest_port, source_id, source_port, message) = packet

		# Get the key
		packet_key = self.buffer_key(dest_port, source_id, source_port, pkt_id)

		# Create the entry
		self.message_buffer[packet_key] = {"last_timestamp" : time.time(), "total_size" : total_size, "data_buffer" : [], "byte_offsets" : []}

		# Return for ease
		return self.message_buffer[packet_key]

	# Makes the key that indexes the buffer
	def buffer_key(self, dest_port, source_id, source_port, pkt_id):

		return " ".join([str (i) for i in [dest_port, source_id, source_port, pkt_id]])

	# The size of the header generated by this layer
	# Expected size
	# Dest node	| Packet ID	| Offset	| Total size	| Dest port	| Source node	| Source port
	# 4		| 4		| 4		| 4		| 4		| 4		| 4
	# Total: 28 
	def header_size(self):

		return (field_size * 7)

	# The total size of the header including the lower layer header
	# Expected size
	# Link layer	| DNP layer
	# 20		| 28
	def header_total(self):

		return self.lower_layer.header_total() + self.header_size()
