from utils.UInt32 import UInt32


class RDTHeader:
    def __init__(self, SYN: int = 0, FIN: int = 0, ACK: int = 0, SEQ_num: int = 0, ACK_num: int = 0, LEN: int = 0,
                 CHECKSUM: int = 0, PAYLOAD=None, RWND: int = 0,
                 test_case: int = 0
                 ) -> None:
        self.test_case = test_case  # Indicate the test case that will be used

        self.SYN = SYN  # 1 bytes
        self.FIN = FIN  # 1 bytes
        self.ACK = ACK  # 1 bytes
        self.SEQ_num = SEQ_num  # 4 bytes
        self.ACK_num = ACK_num  # 4 bytes
        self.LEN = LEN  # 4 bytes
        self.CHECKSUM = CHECKSUM  # 2 bytes
        self.PAYLOAD = PAYLOAD  # Data LEN bytes
        # self.CWND = CWND                      # Congestion window size 4 bytes
        self.RWND = RWND                        # Notification window size 4 bytes
        self.Reserved = 0                       # Reserved field for any attribte you need.

        self.Source_address = [127,0,0,1,12334] # Souce ip and port
        self.Target_address = [127,0,0,1,12345] # Target ip and port


    def to_bytes(self):
        test_case = self.test_case.to_bytes(1, 'big')
        Source_address = self.Source_address[0].to_bytes(1, 'big') + self.Source_address[1].to_bytes(1, 'big') + \
                            self.Source_address[2].to_bytes(1, 'big') + self.Source_address[3].to_bytes(1, 'big') + \
                            self.Source_address[4].to_bytes(2, 'big')

        Target_address = self.Target_address[0].to_bytes(1, 'big') + self.Target_address[1].to_bytes(1, 'big') + \
                            self.Target_address[2].to_bytes(1, 'big') + self.Target_address[3].to_bytes(1, 'big') + \
                            self.Target_address[4].to_bytes(2, 'big')

        SYN = self.SYN.to_bytes(1, 'big')
        FIN = self.FIN.to_bytes(1, 'big')
        ACK = self.ACK.to_bytes(1, 'big')
        SEQ_num = self.SEQ_num.to_bytes(4, 'big')
        ACK_num = self.ACK_num.to_bytes(4, 'big')
        LEN = self.LEN.to_bytes(4, 'big')
        RWND = self.RWND.to_bytes(4, 'big')
        CHECKSUM = self.CHECKSUM.to_bytes(2, 'big')
        PAYLOAD = self.PAYLOAD.encode() if isinstance(self.PAYLOAD, str) else "".encode()
        Reserved = self.Reserved.to_bytes(8, 'big')

        return b''.join([test_case, Source_address, Target_address, SYN, FIN, ACK, SEQ_num, ACK_num, LEN, RWND, CHECKSUM, Reserved, PAYLOAD])


    def from_bytes(self, data):
        self.test_case = data[0]
        Source_address = []
        for i in range(4):
            Source_address.append(data[i + 1])
        Source_address.append(int.from_bytes(data[5:7], 'big'))
        self.Source_address = Source_address

        Target_address = []
        for i in range(4):
            Target_address.append(data[i + 7])
        Target_address.append(int.from_bytes(data[11:13], 'big'))
        self.Target_address = Target_address


        self.SYN = data[13]
        self.FIN = data[14]
        self.ACK = data[15]
        self.SEQ_num = int.from_bytes(data[16:20], 'big')
        self.ACK_num = int.from_bytes(data[20:24], 'big')
        self.LEN = int.from_bytes(data[24:28], 'big')
        self.RWND = int.from_bytes(data[28:32], 'big')
        self.CHECKSUM = int.from_bytes(data[32:34], 'big')
        self.Reserved = int.from_bytes(data[34:42], 'big')

        self.PAYLOAD = data[42:].decode()

        return self

    def __str__(self):
        return f"SYN:{self.SYN}, FIN:{self.FIN}, ACK:{self.ACK}, SEQ_num:{self.SEQ_num}, ACK_num:{self.ACK_num}, " \
               f"LEN:{self.LEN}, CHECKSUM:{self.CHECKSUM}, RWND:{self.RWND}, PAYLOAD:{self.PAYLOAD}, Source:{self.src}, Target:{self.tgt}"

    @staticmethod
    def addr_list(ip_addr: (str, int)) -> [int]:
        return [int(i) for i in ip_addr[0].split('.')] + [ip_addr[1]]

    @staticmethod
    def addr_tuple(addr_list: [int]) -> (str, int):
        return ".".join([str(i) for i in addr_list[:4]]), addr_list[4]

    def __eq__(self, other):
        if not isinstance(other, RDTHeader):
            return False
        return (
                self.SYN == other.SYN and self.FIN == other.FIN and self.ACK == other.ACK and
                self.SEQ_num == other.SEQ_num and self.ACK_num == other.ACK_num
                and self.LEN == other.LEN and self.CHECKSUM == other.CHECKSUM and
                (RDTHeader.__ensure_str(self.PAYLOAD) == RDTHeader.__ensure_str(other.PAYLOAD))
                and self.RWND == other.RWND
                and self.src == other.src and self.tgt == other.tgt)

    def set_src_dest(self, my_address: (str, int), target: (str, int)):
        self.Source_address = RDTHeader.addr_list(my_address)
        self.Target_address = RDTHeader.addr_list(target)

    @staticmethod
    def __ensure_str(value) -> str:
        return value if isinstance(value, str) else ''

    def compute_checksum(self):
        self.CHECKSUM = 0
        # Generate bytes array
        data = self.to_bytes()

        # Split data into 2-byte segments
        segments = [int.from_bytes(data[i:i + 2], 'big') for i in range(0, len(data), 2)]

        # If the data length is odd, add an extra zero byte
        if len(data) % 2 != 0:
            segments.append(int.from_bytes(data[-1:] + b'\x00', 'big'))

        # Sum all 16-bit values
        total_sum = sum(segments)

        # Add overflow from high bits to low bits
        while total_sum > 0xFFFF:
            total_sum = (total_sum & 0xFFFF) + (total_sum >> 16)

        # Calculate one's complement
        checksum = ~total_sum & 0xFFFF

        # Set the checksum in the object
        self.CHECKSUM = checksum

    def packet_verify(self) -> bool:

        '''
        TODO enable pkt verify
        :return:
        '''
        t_checksum = self.CHECKSUM
        self.compute_checksum()

        if(self.CHECKSUM != t_checksum):
            print("Error HERE!")
        # return self.CHECKSUM == 0xFFFF
        return self.CHECKSUM == t_checksum


    @staticmethod
    def get_from_bytes(data: bytes):
        pkt = RDTHeader()
        return pkt.from_bytes(data)

    def get_payload(self):
        return self.PAYLOAD

    def set_payload(self, payload):
        self.PAYLOAD = payload
    def assign_address(self, Source_address: tuple, Target_address: tuple):
        source_ip = Source_address[0].split('.')
        target_ip = Target_address[0].split('.')
        for i in range(4):
            self.Source_address[i] = int(source_ip[i])
            self.Target_address[i] = int(target_ip[i])
        self.Source_address[4] = Source_address[1]
        self.Target_address[4] = Target_address[1]

    @property
    def src(self):
        return (f"{self.Source_address[0]}.{self.Source_address[1]}.{self.Source_address[2]}.{self.Source_address[3]}", self.Source_address[4])

    @property
    def tgt(self):
        return (f"{self.Target_address[0]}.{self.Target_address[1]}.{self.Target_address[2]}.{self.Target_address[3]}", self.Target_address[4])


class PacketType:
    @staticmethod
    def get_SYN(SEQ_num: UInt32) -> RDTHeader:
        return RDTHeader(SYN=1, SEQ_num=int(SEQ_num),test_case=20)

    @staticmethod
    def add_ACK(pkt: RDTHeader, ACK_num: UInt32,test_case:int = None) -> RDTHeader:
        pkt.ACK = 1
        pkt.ACK_num = int(ACK_num)
        if test_case is not None:
            pkt.test_case = test_case
        return pkt

    @staticmethod
    def get_ACK(SEQ_num: UInt32, ACK_num: UInt32,test_case:int) -> RDTHeader:
        return RDTHeader(ACK=1, SEQ_num=int(SEQ_num), ACK_num=int(ACK_num),test_case=test_case)

    @staticmethod
    def get_RST() -> RDTHeader:
        # TODO RST PKT
        return RDTHeader(FIN=2)

    @staticmethod
    def get_FIN(SEQ_num: UInt32):
        return RDTHeader(FIN=1, SEQ_num=int(SEQ_num),test_case=20)

    @staticmethod
    def set_data_out(data:RDTHeader, SEQ_num:UInt32):
        '''
        must be used for pkt to send out while data transmission
        :param data:
        :param SEQ_num:
        :return:
        '''
        data.LEN=len(data.PAYLOAD)
        data.SEQ_num=int(SEQ_num)
        return data


