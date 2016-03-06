# Constructs a packet based on the type and other options

import hashlib

# This is the delimiter used to separate packet meta fields
delimiter = "|"

# Get the size of every hash
hash_size = hashlib.md5().digest_size

# Types of supported packets:
#
# ping, 1
# This packet sends no valuable data, it just checks for an active host


# This dictionary maps string identifiers of packets to int ids
name_to_id = {
	"ping" : 1
}

# Maps the ids to the common names
id_to_name = dict ( (v,k) for k, v in name_to_id.items() )
"""
# Uses md5 to return the hash value for the sent string
def get_hash(sent):

	# Make the md5 hasher
	hasher = hashlib.md5()

	# Add the string
	hasher.update(sent)

	# Return the hash
	return hasher.digest()

# Checks the hash at the start of the packet
# Returns bool
def check_valid(packet):

	# Separate the hash from the rest of the packet
	sent_hash = packet[:hash_size]
	packet_body = packet[hash_size:]

	# Get the hash for the packet_body
	packet_hash = get_hash(packet_body)

	# Return the comparision
	return sent_hash == packet_hash
"""
# Creates a packet based on the option sent, defined above
# Other arguments are specific to the type of packet being sent
def make_packet(packet_type, type_args):

	# If type_args isn't a tuple/list, pack it into a tuple for simplicity
	try:

		type_args[0]

	except TypeError:

		type_args = (type_args,)

	# If the packet_type is a string identifier, get the id for it
	try:

		packet_type = name_to_id[packet_type]

	# The packet type does not exist
	except KeyError:

		raise ValueError("Packet type not known: " + str(packet_type))

	# Ping
	if packet_type == 1:

		# Uses only the ping number
		return make_ping(type_args[0])

	# Unknown type
	else:

		raise ValueError("Packet type not known: " + str(packet_type))

# Creates a blank message used for pinging
def make_ping(ping_msg):

	packet_id = name_to_id["ping"]

	# Just send the ping_content
	#packet_content = str(ping_msg)

	# Create the packet body
	#packet_body = delimiter.join([str(i) for i in [packet_id, ping_msg]])

	# Hash the packet body
	packet_hash = get_hash(packet_body)

	# Add the hash to the start of the packet
	packet_total = packet_hash + packet_body

	return packet_total

# Checks for packet validity and gets the contents based on the type
# Raises RuntimeError if the packet is corrupted
def unpack(packet):

	# Check for packet validity
	#if not check_valid(packet):

	#	raise RuntimeError("Packet is corrupted")

	# Remove the hash from the packet and get the contents
	return get_contents(packet[hash_size:])
"""
# Gets packet contents based on the type (type must be first token in the packet)
def get_contents(packet_body):

	# Get the packet type and other contents
	(packet_type, packet_remaining) = packet_body.split(delimiter, 1)
	packet_type = int(packet_type)

	# Ping
	if packet_type == 1:

		return id_to_name[packet_type], unpack_ping(packet_remaining)

	# Unknown
	else:

		raise ValueError("Packet type not known: " + str(packet_type))

# Unpacks a ping, first token must be packet content
# Kind of a pointless function, but important for completeness
# Returns ping_number
def unpack_ping(packet_contents):

	return packet_contents
"""
