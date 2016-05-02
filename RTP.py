# Reliable transport protocol
# Sends messages that are checked for arrival
# Header:
# type | sequence number

import logging
import time
import os
import base64
import re

from general_utility import *

# Gets the window from the packet, used for peeking
def get_window(packet):

	# Get the readable form of the packet
	(dest_port, source_id, source_port, message) = packet

	# Separate the header from the body
	#header = message[:gen_header_size()]
	#body = message[gen_header_size():]

	# Get the pkt type and sequence num
	#(pkt_type, sequence_num) = [int(x) for x in unpack_string(message[:8])]
	pkt_type, sequence_num, total_size, body = [int(x) for x in message.split('|')]

	# Get the total_size
	#(total_size, body) = message[8:].split("|", 1)
	#total_size = int(total_size)

	return int(body)

# The size of the header generated by this layer
# Expected size
# type	| sequence number
# 4	| 4
# Total: 8
def gen_header_size():

	return (field_size * 2)

# The total size of the header including the lower layer header
# Expected size
# DNP layer	| RTP layer
# 48		| 8
def gen_header_total():

	return self.DNP.header_total() + self.header_size()

class RTP:

	# timeout determines how long to wait for AKs of any kind
	# Set target port if this is accepting a request
	def __init__(self, node_id, service_id, DNP, target_id, connected_to, target_port=None, listen_port=10, timeout=.5, window=5, default_max = 500):

		self.node_id = node_id

		# The service id of this connection
		self.service_id = service_id

		# The id of the node being communicated to
		self.target_id = target_id

		# For tracking connected ports
		self.connected_to = connected_to

		# The port for requesting new connections
		self.listen_port = listen_port

		# This is used to send single packets
		self.DNP = DNP

		# This is the timeout for cleanup duties
		self.timeout=timeout

		# This is the timeout for closing the service
		self.close_timeout = 6 * self.timeout

		# This is the number of packets to allow in flight
		self.window = window

		# The is how big to make packets by default in bytes
		self.default_max = default_max

		# If the connection is active
		self.connected = False

		# Tracks the stage in the stream
		# 1 - request connection
		# 2 - accept a request
		# 3 - finalize handshake
		# 4 - active
		self.stage = 1

		# Counters for each handshake stage
		self.request_counter = 0
		self.accept_counter = 0
		self.finalize_counter = 0

		# Max values for each counter
		self.request_max = 6
		self.accept_max = 6
		self.finalize_max = 6

		self.reset_trackers()

		self.last_clean = 0

		# Make sure the folder exists
		enforce_path(os.path.join(content_folder, str(self.node_id)))

		# If target port is sent, advance stage and set port
		if target_port:

			self.stage = 2

			self.target_port = target_port

			# Send the accept message
			self.accept()

		# Otherwise, initiate the connection
		else:

			self.request()

	# Opens new packets
	def serve(self, packet):

		#print packet

		# Get the readable form of the packet
		(dest_port, source_id, source_port, message) = packet

		# Separate the header from the body
		#header = message[:self.header_size()]
		#body = message[self.header_size():]

		# Get the header info
		#(pkt_type, sequence_num, total_size) = unpack_string(header)
		#pkt_type = int(pkt_type)
		#sequence_num = int(sequence_num)
		#total_size = int(total_size)

		(pkt_type, sequence_num, total_size, body) = self.separate(message)

		# Execution depends on connection state and packet type

		# Request
		# Not needed here?
		if pkt_type == 1:

			# Window size
			self.window = int(message)

			# Set the target based on the sender service id
			self.target_port = source_port

			self.accept()

			if self.stage < 2:
				self.stage = 2

		# Accept
		elif pkt_type == 2:

			# Set the target based on the sender service id
			self.target_port = source_port

			# Time since last finalize
			self.last_finalize = time.time()

			self.finalize()

			if self.stage < 3:
				self.stage = 3

		# Finalize
		elif pkt_type == 3:

			if self.stage < 4:
				self.stage = 4

				logging.warning("Established connection to: " + str(self.target_id))

				# Add to the connected list
				self.connected_to.append((self.service_id, self.target_id, self.target_port))

		# Content message
		elif pkt_type == 5:

			# Bundle content
			packet_info = (sequence_num, total_size, body)

			# Get the content
			self.unpack_content(packet_info)

		# AK
		elif pkt_type == 6:

			self.aked(sequence_num)

		# File request
		elif pkt_type == 10:

			# Get the name of the requested file
			file_name = body

			# Try to open the file
			try:

				with open(os.path.join(content_folder, str(self.node_id), file_name), 'rb') as the_file:

					# Get all of the file contents
					#self.file_contents = base64.b64encode(the_file.read())
					self.file_contents = the_file.read().encode('base64')

			# File doesn't exist
			except IOError:

				self.DNE()

			# Send the yes response and start sending content
			else:

				# Connection may already be in use
				try:

					self.send(self.file_contents)

				except RuntimeError:

					pass

				else:

					self.window_send()
					self.yes()

		# File response
		elif pkt_type == 11:

			# Accepted
			if body == 'yes':

				# Unset flag, content is incoming
				self.requested = False

			# File doesn't exist
			elif body == 'DNE':

				# Abort content request
				self.reset_trackers

				logging.warning("Download failed, file does not exist")

		# Not known type
		else:

			logging.error("Packet type not known: " + str(pkt_type))

	# Sends a message reliably
	def send(self, message, chunk_size=None):

		if chunk_size is None:
			chunk_size = self.default_max

		if len(self.all_queue.keys()) != 0:

			raise RuntimeError("Connection is busy")

		# Reset the trackers, timing depends on it
		self.reset_trackers()

		# Save the total size of the message
		message_total = len(message)

		start = 0
		offset = chunk_size
		message_parts = []
		while offset < message_total:

			message_parts.append(message[start:offset])

			start += chunk_size
			offset += chunk_size

		if start < message_total:

			message_parts.append(message[start:])

		# Add all of the messages to the queue
		tot = 0
		start_counter = self.packet_counter
		for packet_id in range(start_counter, len(message_parts) + start_counter):

			tot += len(message_parts[packet_id - self.packet_counter])

			self.all_queue[packet_id] = self.make_header(5,packet_id, message_total) + message_parts[packet_id - self.packet_counter]

	# Sends the messages currently in the window
	def window_send(self):

		#print " first ", sorted(self.all_queue.keys())[:self.window]

		# Ignore if there is nothing to send
		if len(self.all_queue.keys()) != 0:

			# Get a window of messages
			send_candidates = sorted(self.all_queue.keys())[:self.window]

			# Send any that are not waiting on AKs
			for candidate in send_candidates:

				# Check for freshness
				#if candidate not in self.ak_waiting:
				if True:

					# It is now waiting on ak
					if candidate not in self.ak_waiting:
						self.ak_waiting.append(candidate)

					#print candidate

					# Send the content of this message
					self.send_single(candidate)

	# Sends one message from the queue
	def send_single(self, send_num):
		#print "Sending: ", send_num

		# Get the message out of the queue
		message = self.all_queue[send_num]

		#print message

		#print len(message)

		# Send it
		try:
			self.DNP.send(message, self.target_id, self.target_port, self.service_id)
		except KeyError:
			#print "s no"
			pass
		#print 'k'

	# Buffers content
	def unpack_content(self, packet):

		self.last_content = time.time()

		(sequence_num, total_size, body) = packet

		# New stream, set the total size
		if self.total_size is None:

			self.total_size = total_size

		# New content
		if sequence_num not in self.content_ids:

			# Add to the ledger
			self.content_ids.append(sequence_num)
			self.content_ids.sort()

			# Get the location to add
			index = self.content_ids.index(sequence_num)

			# Add the content to the buffer
			self.content_buffer.insert(index, body)

		# AK the packet
		self.ak(sequence_num)

	# AKs a packet
	def ak(self, num):

		if num not in self.send_aks:
			self.send_aks.append(num)

		#self.DNP.send(self.make_header(6,num,0), self.target_id, self.target_port, self.service_id)

	# Sends all aks
	def window_ak(self):

		#print self.send_aks

		for item in self.send_aks:

			try:
				self.DNP.send(self.make_header(6,item,0), self.target_id, self.target_port, self.service_id)
			except KeyError:
				#print "no"
				pass

		# Clear the list
		self.send_aks = []

	# Asks for a file
	def ask(self, file_name=None):

		if file_name is not None:

			self.file_name = file_name

		elif file_name is None:

			return None
		try:
			self.DNP.send(self.make_header(10,0,0) + self.file_name, self.target_id, self.target_port, self.service_id)
		except KeyError:
			#print "no"
			pass

	# Sends file acceptance
	def yes(self):
		try:
			self.DNP.send(self.make_header(11,0,0) + 'yes', self.target_id, self.target_port, self.service_id)
		except KeyError:
			pass

	# Sends file reject
	def DNE(self):
		try:
			self.DNP.send(self.make_header(11,0,0) + 'DNE', self.target_id, self.target_port, self.service_id)
		except KeyError:
			pass

	# Deals with AK
	def aked(self, num):

		self.last_ak = time.time()

		# Remove from the waiting and queue
		#if num in self.ak_waiting:
		if num in self.all_queue.keys():

			#self.ak_waiting.remove(num)

			#if result == None:
			#	self.ak_waiting = []

			del self.all_queue[num]

			if len(self.all_queue.keys()) == 0:
				#logging.warning("Download complete")
				self.done = True

	# Attempts to get the content
	def get_content(self):

		# Combine all data
		combined_data = "".join(self.content_buffer)

		#print "buffer: ", len(combined_data), " ", self.total_size

		# Packet is complete if size of data is equal to the total_size
		if self.total_size and len(combined_data) == self.total_size:

			# Set flag
			#print "Content got"
			self.done = True

			# Stop counters
			self.last_content = None

			# Send back all data
			return combined_data

		# Not complete
		else:

			return None

	# Saves the content
	def save_content(self):

		#print "len content buffer", len(self.content_buffer)

		# Ignore if there is no content
		if len(self.content_buffer) != 0:

			# Try to get the content
			content = self.get_content()

			# Content got
			if content is not None:

				# Get the total time
				total_time = time.time() - self.start_time

				# Need to go from utf-8 -> base64 -> file
				content = content.decode('utf-8')
				content = content.decode('base64')

				# Get the size of the content
				content_size = len(content)

				logging.warning("File downloaded: " + self.file_name + " time taken: " + str(total_time) + " bandwidth (bytes/second): " + str(content_size / total_time))

				# Save it
				with open(os.path.join(content_folder, str(self.node_id), self.file_name ), 'w') as the_file:

					the_file.write(content)

	# Does maintainence on the connection
	def cleanup(self):

		# Based on stage, do cleanup

		# Requesting
		if self.stage == 1:

			# Resend request
			self.request()

		# Accepting
		elif self.stage == 2:

			# Resend accept
			self.accept()

		# Finalizing
		elif self.stage == 3:

			# If no accepts have been recieved in a while, connection is active
			if(self.last_finalize_time and self.last_finalize_time > self.timeout*self.accept_max):

				self.stage = 4

				logging.warning("Finalized connection to: " + str(self.target_id))

				# Add to the connected list
				self.connected_to.append((self.service_id, self.target_id, self.target_port))

			else:

				# Resend finalize
				self.finalize()

		# Active
		else:

			#print len(self.all_queue)#, " ", len(self.send_aks)

			# Make sure enough time has passed
			if time.time() - self.last_clean > self.timeout:

				self.last_clean = time.time()

				# Check for response ak
				if self.requested:

					self.ask(self.file_name)

				# Stream is not complete
				if not self.done:

					#print "not done"

					# Check for content timeout
					if self.last_content and time.time() - self.last_content > self.timeout:

						#print "content time out"

						# Check for broken
						if time.time() - self.last_content > self.timeout * 10:

							raise RuntimeError("Connection broken")

						#else:

							#self.

					# Check for ak timeout
					if self.last_ak and time.time() - self.last_ak > self.timeout:

						#print "ak time out"

						# Check for broken
						if time.time() - self.last_ak > self.timeout * 10:

							raise RuntimeError("Connection broken")

					# Resend content
					self.window_send()

					# Resend aks
					self.window_ak()

					# Try to get all content
					self.save_content()

	# Sends a request, step 1 in handshake
	def request(self):

		logging.info("Requesting connection with: " + str(self.target_id))

		# Increment counter
		self.request_counter += 1

		# If this has reached max, throw an error
		if self.request_counter > self.request_max:

			raise RuntimeError("Request limit reached")

		# Get the header for the packet
		# This is also the only content
		#message = pack_string([1,0,0]) + str(self.window)
		message = self.make_header(1,0,0) + str(self.window)

		# Send this message
		try:
			self.DNP.send(message, self.target_id, self.listen_port, self.service_id)
		except KeyError:
			pass

	# Accepts the request and replies with the AK, step 2 in handshake
	def accept(self):

		logging.info("Accepting connection from: " + str(self.target_id) + " connecting to port: " + str(self.target_port))

		# Increment counter
		self.accept_counter += 1

		# If this has reached max, throw an error
		if self.accept_counter > self.accept_max:

			raise RuntimeError("Accept limit reached")

		# Get the header for the packet
		# This is also the only content
		#message = pack_string([2,0,0])
		message = self.make_header(2,0,0)

		# Send this message
		try:
			self.DNP.send(message, self.target_id, self.target_port, self.service_id)
		except KeyError:
			pass

		# Add to the connected list
		#self.connected_to.append((self.target_id, self.target_port))

	# Finalizes handshake, step 3 in handshake
	def finalize(self):

		try:
			self.last_finalize_time

		except AttributeError:
			self.last_finalize_time = time.time()

		logging.info("Finalizing connection with: " + str(self.target_id))

		# Increment counter
		self.finalize_counter += 1

		#self.last

		# If this has reached max, throw an error
		if self.finalize_counter > self.finalize_max:

			raise RuntimeError("Finalize limit reached")

		# Get the header for the packet
		# This is also the only content
		#message = pack_string([3,0,0])
		message = self.make_header(3,0,0)

		# Send this message
		try:
			self.DNP.send(message, self.target_id, self.target_port, self.service_id)
		except KeyError:
			pass

		# Add to the connected list
		#self.connected_to.append((self.target_id, self.target_port))

	# Resets connection trackers
	# Use after complete transfer
	def reset_trackers(self):

		# The time the transfer was started
		self.start_time = time.time()

		# The packet ID counter
		self.packet_counter = 1

		# The total queue of packets
		# Sequence number : content
		self.all_queue = {}

		# The packet IDs waiting AK
		self.ak_waiting = []

		# The last time content was got
		self.last_content = None

		# The last time AK was got
		self.last_ak = None

		# Expected content size
		self.content_size = None

		# Connection is completed
		self.done = False

		# Request was made
		self.requested = False

		# File name asked for
		self.file_name = None

		# The expected content size
		self.total_size = None

		# Content buffer
		self.content_buffer = []

		# Sequence nums in the buffer
		self.content_ids = []

		# The aks to send
		self.send_aks = []

	# Makes the header
	def make_header(self, pkt_type, sequence_num, total_size):

		#return pack_string([pkt_type]) + str(sequence_num) + '|' + str(total_size) + "|"

		return "|".join([str(x) for x in [pkt_type, sequence_num, total_size]]) + '|'

	# Gets the header, body
	def separate(self, packet):

		# Get the pkt type and sequence num
		#(pkt_type,) = [int(x) for x in unpack_string(packet[:8])]

		# Get the total_size
		#(total_size, body) = packet[8:].split("|", 1)
		#total_size = int(total_size)

		(pkt_type, sequence_num, total_size, body) = packet.split("|", 3)
		pkt_type = int(pkt_type)
		sequence_num = int(sequence_num)
		total_size = int(total_size)

		#return pkt_type, sequence_num, total_size, body
		return (pkt_type, sequence_num, total_size, body)

	# The size of the header generated by this layer
	# Expected size
	# type	| sequence number	
	# 4	| 4			
	# Total: 8
	def header_size(self):

		return (field_size * 2)

	# The total size of the header including the lower layer header
	# Expected size
	# DNP layer	| RTP layer
	# 48		| 8
	def header_total(self):

		return self.DNP.header_total() + self.header_size()
