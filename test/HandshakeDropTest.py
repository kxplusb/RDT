import time
import unittest

from Connection import handshake
from Header import RDTHeader
from RDT import RDTSocket

# 测试三握四挥
data = "1"


class HandshakeTest(unittest.TestCase):
    def test_no_drop(self):
        with handshake(data=data) as ((udp_send,udp_recv),check_connection_established):
            pkt: RDTHeader = udp_recv.recv_pkt()
            assert pkt.SYN ==1
            udp_send.send(pkt)

            pkt: RDTHeader = udp_send.recv_pkt()
            assert pkt.ACK==1 and pkt.SYN==1
            udp_recv.send(pkt)

            pkt:RDTHeader = udp_recv.recv_pkt()
            assert pkt.ACK==1
            udp_send.send(pkt)

            time.sleep(1)
            assert check_connection_established()

