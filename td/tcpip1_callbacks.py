# me - this DAT
#
# dat - the DAT that received the data
# rowIndex - the row number the data was placed into
# message - an ascii representation of the data
#			Unprintable characters and unicode characters will
#			not be preserved. Use the 'byteData' parameter to get
#			the raw bytes that were sent.
# byteData - a byte array of the data received
# peer - a Peer object describing the originating data
#   peer.close() 	#close the connection
#	peer.owner	#the operator to whom the peer belongs
#	peer.address	#network address associated with the peer
#	peer.port		#network port associated with the peer

def onConnect(dat, peer):
    print(f"[tcpip] onConnect {peer}")
    return


def onReceive(dat, rowIndex, message, byteData, peer):
    print(f"[tcpip] onReceive {peer} {rowIndex} {message} {byteData}")
    text1_dat =  op('text1')
    print(f"[tcpip] text1_dat: {text1_dat}")
    has_interface = hasattr(text1_dat, 'interface')
    print(f"[tcpip] has_interface: {has_interface}")
    if has_interface:
        print(f"[tcpip] let text1_data to call onReceive")
        op('text1').interface.onReceive(dat)  # dat 是 tcpip1


def onClose(dat, peer):
    print(f"[tcpip] onClose {peer}")
    return

