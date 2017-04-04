# OSI Layer Simulation
 
The purpose of this project is to rebuild most of the networking stack.
Layers included are:
* Link
* Network
* Transport
* Application

Ultimately, the protocol must be able to send files between any two nodes in the network given the following concerns:
* Nodes may have to be communicate indirectly through neighbors
* Links between neighbors may drop or corrupt packets
* Nodes may fail at any time
* Links have a maximum transmission unit, which is often smaller than the files
