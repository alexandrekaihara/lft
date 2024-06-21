from datetime import datetime, timedelta
from json import load
from results.preprocess import Preprocess
from experiment.constants import *


class Latency(Preprocess):
    def get(self, json, keyName):
        if keyName == LATENCY:
            latencies = self._getLatencies(json)
            return [latency for latency in latencies if latency > 0]
        
    def _getLatencies(self, json) -> list:
        packets = json["raw-packets"]
        return [self.__getLatency(packet["src-ts"], packet["dst-ts"]) for packet in packets]

    def getJitters(self, latencies: list) -> list:
        return [latencies[i] - latencies[i+1] for i in range(len(latencies)-2)]

    def __getLatency(self, src_timestamp, dst_timestamp):
        return dst_timestamp - src_timestamp
        #src = self.__timestampToUTC(src_timestamp)
        #dst = self.__timestampToUTC(dst_timestamp)
        #return dst.microsecond - src.microsecond
    
    def __timestampToUTC(self, ntp_timestamp) -> datetime:
        ntp_epoch = datetime(1900, 1, 1)
        ntp_seconds = int(ntp_timestamp >> 32)
        ntp_fraction = int((ntp_timestamp & 0xFFFFFFFF) * 1e9 / 0xFFFFFFFF)
        return ntp_epoch + timedelta(seconds=ntp_seconds) + timedelta(microseconds=ntp_fraction // 1000)


