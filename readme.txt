David Frank
CPE 701 Semester Project

Quick Start:

Use python node.py -h to find out what parameters the node needs to run. Once running, more info will be provided by a menu inside the application. Any content you want to send will need to be placed into the 'content' sub folder. This is to prevent the root folder from being overwhelmed by files.

Longer Start:

Make sure that there is a topology file that can be run. It is advised to place it into the 'topology' sub folder. To run a node, it needs at least a node_id and a topology_file, ex: python node.py 1 local_test_1.txt . Other options will change the node parameters or the output. Loss chance and corruption chance change the garbler parameters. Logger level sets the verbosity of the log. Logger file will redirect all log messages to the specified file, it is advised to place this file into the 'log' sub folder.

Once the node is running, there are a few commands the user can do, as shown in the menu. You can always see the menu again by typing menu. If a command gets interrupted by a message, just keep typing. The command will still be parsed correctly. 'quit' will exit the node. This is advised since it will allow for shut down actions.

Some show info about the node. These are:
routing : shows the current routing table, good for seeing the topology change when a node or link fails
services : shows the IDs of active download services. Other nodes can connect to these.
links : shows the status of the linked neighbors. Gives basic info and states if that link is currently active, based on downLink and upLink commands.
connections : shows the connections this node can use to download files

Some commands change the parameters of the node, such as:
setGarble [loss] [corruption] : sets the garbler parameters, you can send 'SAME' for a parameter you don't want to change
downLink [neighbor id] : deactivates the link to the specified neighbor. Nothing can be sent over the link, use upLink to bring it back.
upLink [neighbor id] : reactivate the link to the specified neighbor. Packets can now be sent over the link again.

Some commands allow the user to interact with other nodes, such as:
message [node id to send to] [what to send] : sends an unreliable packet to the specified node that will be printed onto the screen
startService [max_connections] : starts a download service that other nodes can connect to. Will show the id of the service that was just created
connectTo [target id] [target service] [window] : connect to another node's download service. The window sets the sliding window of the RTP protocol used for this connection.
download [connection id] [file name] : Once you are connected to a download service, you can download files from the other node. These files will be placed into the content sub folder with the name [this_node_id]_[orginal_file_name]
