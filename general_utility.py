# This contains general utility functions

import os
import errno

import hashlib
import struct

# The size of !L fields packed by struct
field_size = struct.calcsize("!L")

# Enforces file path
def enforce_path(path):
    try:
	os.makedirs(path)
    except OSError as exc: # Python >2.5
	if exc.errno == errno.EEXIST and os.path.isdir(path):
	    pass
	else: raise

# Takes a list of numbers and packs them into a string using !L
def pack_string(to_pack):

	# If a single number has been sent, make it a tuple for simplicity
	try:

		to_pack[0]

	except TypeError:

		to_pack = (to_pack,)

	# Place all the arguments into a string
	packed = struct.pack("!" + "L"*len(to_pack), *to_pack)

	return packed

# Takes a string and unpacks numbers assuming that all numbers are size field_size
def unpack_string(to_unpack):

	# Get the amount of numbers
	amount = len(to_unpack) / field_size

	# Unpack
	unpacked = struct.unpack("!" + "L"*amount, to_unpack)

	return unpacked

# Opens topology file and returns information about the node with the sent name
# (ip, port, connection1, connection2, mtu)
def get_topology_from_file(file_name, node_id):

	# Open topology file
	with open(file_name) as config_file:

		# Go through each line
		for line in config_file:

			# Ignore lines that do not correspond to this node_id, which should be the first token in the line
			line_contents = line.split()
			line_id = line_contents[0]
			if line_id == node_id:

				# Get all of the relevant info from the line
				ip = line_contents[1]
				port = int(line_contents[2])
				connection1 = line_contents[3]
				connection2 = line_contents[4]
				mtu = line_contents[5]

	# If no items were found, then this node is not in the file
	try:

		ip

	except UnboundLocalError:

		raise ValueError("Node ID not in file: " + str(node_id))

	return ip, port, connection1, connection2, mtu
