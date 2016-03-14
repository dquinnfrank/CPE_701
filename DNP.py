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
	def __init__(self, node_id, routing_layer, buffer_timeout = .5, upper_layer = None):

		self.node_id = node_id

		# Holds information about next hops and link mtus
		self.routing_layer = routing_layer

		self.buffer_timeout = buffer_timeout

		# Save the upper layer if there is one
		self.upper_layer = upper_layer

		# A number that is used to create packet ids
		self.packet_counter = 0

		# Holds fragmented messages
		# packet_key : [last_timestamp, total_size, data_buffer, byte_offsets]
		self.message_buffer = {}

		# The link layer that will handle lower level communication
		self.lower_layer = link.Link(self)

	# Creates a best effort service packet
	# Returns a list of strings with the packet header and content
	# Each item in the list is a fragment of the packet, commonly there will only be one
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
		offset_counter = 0 # Tracks the chunk number
		while len(message_remaining) > max_size:

			# Take a chunk of the message off and make a packet out of it
			message_chunk = message_remaining[:max_size]

			# Pack and add to the message list
			to_send = self.single_pack(message_chunk, destination_id, destination_port, source_port, TTL = TTL, offset = offset_counter, total_size = message_size)
			message_fragments.append(to_send)

			# Remove the packed message
			message_remaining = message_remaining[max_size:]

		# Get the remainder of the message
		if len(message_remaining) > 0:

			to_send = self.single_pack(message_remaining, destination_id, destination_port, source_port, TTL = TTL, offset = offset_counter, total_size = message_size)
			message_fragments.append(to_send)

		# Incrment count
		offset_counter += 1

		return message_fragments

	# Makes a single packet, size must be less than the mtu
	def single_pack(self, message, destination_id, destination_port, source_port, TTL = None, offset = 0, total_size = None):

		# If total is None, use the size of the message as the total
		if total_size is None:

			total_size = len(message)

		# Get the binary header for the DNP portion of the message
		DNP_header = pack_string([destination_id, self.packet_counter, offset, total_size, destination_port, self.node_id, source_port])

		# Concatinate with the body to make the DNP portion of the packet
		DNP_partial_packet = DNP_header + message

		# Finish the packet by adding the link layer info
		whole_packet = self.lower_layer.pack(DNP_partial_packet, TTL=TTL)

		# Increment the overall packet counter to keep IDs unique
		self.packet_counter += 1

		return whole_packet

	def unpack(self, packet):

		pass

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
