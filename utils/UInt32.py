class UInt32:
    __INF = 2 ** 32

    @staticmethod
    def INF():
        return UInt32.__INF

    def __init__(self, value: int):
        if value < 0 or value > 2 ** 32 - 1:
            raise f'value out of range!:{value}'
        self.__value = value

    def __add__(self, other):
        val = int(other)
        return UInt32((self.__value + val) % (2 ** 32))

    def __sub__(self, other):
        val = int(other)
        return self.__add__(-val)

    def __eq__(self, other):
        return self.__value == int(other)

    def __hash__(self):
        return hash(self.__value)

    def __str__(self):
        return str(self.__value)

    def __repr__(self):
        return f"UInt32({self.__value})"

    def __int__(self):
        return self.__value

    def __lt__(self, __value):
        return self.__value < int(__value)

    def __le__(self, __value):
        return self.__value <= int(__value)

    def __gt__(self, __value):
        return self.__value > int(__value)

    def __ge__(self, __value):
        return self.__value >= int(__value)


