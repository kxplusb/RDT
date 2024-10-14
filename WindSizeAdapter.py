from enum import Enum


class Event(Enum):
    timeout = 0
    ack = 1
    dup_ack = 2


class State(Enum):
    slow_start = 0
    congestion_avoidance = 1
    fast_recovery = 2
    aggressive = 3


class WindSizeAdapter:
    def __init__(self, ssthresh: int, rwnd: int):
        self.cwnd = 1
        self.rwnd = rwnd
        self.ssthresh = ssthresh
        self.state = State.slow_start
        self.last_add_cycle = 0

    def enter_aggressive(self):
        self.state = State.aggressive
        self.rwnd = self.cwnd = 700

    def wind_size(self, event: Event, cycle: int) -> int:  # cwnd (外部rwnd和cwnd取min)
        if (self.state == State.slow_start):
            if (event == Event.ack):
                self.cwnd += 1
                if (self.cwnd >= self.ssthresh):
                    self.state = State.congestion_avoidance
            elif (event == Event.dup_ack):
                self.ssthresh = self.cwnd / 2
                self.cwnd = self.ssthresh
                self.state = State.fast_recovery
            elif (event == Event.timeout):
                self.ssthresh = self.cwnd / 2
                self.cwnd = 1
        elif (self.state == State.congestion_avoidance):
            if (event == Event.ack):
                if (self.last_add_cycle < cycle):
                    self.cwnd += 1
                    self.last_add_cycle = cycle
            elif (event == Event.dup_ack):
                self.ssthresh = self.cwnd / 2
                self.cwnd = self.ssthresh + 3
                self.state = State.fast_recovery
            elif (event == Event.timeout):
                self.ssthresh = self.cwnd / 2
                self.cwnd = 1
                self.state = State.slow_start
        elif (self.state == State.fast_recovery):
            if (event == Event.ack):
                self.cwnd = self.ssthresh
                self.state = State.congestion_avoidance
            elif (event == Event.dup_ack):
                self.cwnd += 1
            elif (event == Event.timeout):
                self.ssthresh = self.cwnd / 2
                self.cwnd = 1
                self.state = State.slow_start
        elif (self.state == State.aggressive):
            self.cwnd = self.rwnd = 700
        if(self.state != State.aggressive):
            return int(max(min(self.cwnd, self.rwnd, 8), 2))
        return int(min(self.cwnd, self.rwnd))


