# Tests the garbler to ensure that the loss / corruption is working correctly

import socket
import sys
import os
import logging

from general_utility import enforce_path
from UDP_socket import UDP_socket

# The IP or host name to use
host_name = "localhost"

# Buffer size for recv
buffer_size = 1024

# The port to send from
send_port = 17878

# The port to recv from
recv_port = 17879

# The message that each message will contain. Check for corruption using this
test_message = "This is a test message"

# This will test the garbled_send function that emulates an unreliable network
# For quicker tests, set number_to_send lower especially when testing high loss rates
def test(loss_threshold = 25, corruption_threshold = 25, number_to_send = 10000):

	print "Testing garbler with parameters:"
	print "Loss Threshold:            " + str(loss_threshold)
	print "Corruption Threshold:      " + str(corruption_threshold)
	print "Number of packets to send: " + str(number_to_send)

	# Create the socket to send messages from
	sender = UDP_socket(host_name, send_port, loss_threshold, corruption_threshold)

	# Socket to get messages from
	recv = UDP_socket(host_name, recv_port)

	# Set the timeout on the recv socket so that losses won't block indefinitely
	recv.sock.settimeout(.1)

	# Run the test
	received_total = 0	# Tracks packets that were recv, for checking loss rate
	received_uncorrupted = 0	# Tracks packets that did not have errors, for checking corruption rate
	print ""
	for packet_index in range(number_to_send):

		padding = len(str(number_to_send)) + 2
		print "\rSending message: " + str(packet_index).ljust(padding) + "Total received: " + str(received_total).ljust(padding) + "Total uncorrupted: " + str(received_uncorrupted).ljust(padding),
		sys.stdout.flush()

		# Send a message
		sender.send_garbled(test_message, (host_name, recv_port))

		# Attempt to get the message
		try:

			get_message = recv.sock.recv(buffer_size)

		# Socket timedout, packet was lost
		except socket.timeout:

			pass

		# Got a message
		else:

			# Increment recv counter
			received_total += 1

			# Check for error
			if get_message == test_message:

				# No error
				received_uncorrupted += 1

	print ""

	# Get the loss rate
	loss_rate = 1 - (float(received_total) / float(number_to_send))

	# Corruption rate
	corruption_rate = 1 - (float(received_uncorrupted) / float(received_total))

	print "Loss rate:       " + str(loss_rate)
	print "Corruption rate: " + str(corruption_rate)

# Run the test with several different parameters
if __name__ == "__main__":

	# No arguments means log to default file
	if len(sys.argv) < 2:

		log_to = "logs/default.log"

	# Get the name of the log file output
	else:

		log_to = sys.argv[1]

		# Can create one directory level if needed
		make_dir, ignore = os.path.split(log_to)
		enforce_path(make_dir)

	logging.basicConfig(filename=log_to, level=logging.INFO)

	print "Default values test"
	test()
