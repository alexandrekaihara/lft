from json import load
from results.preprocess import Preprocess
from experiment.constants import *


class Rtt(Preprocess):
    def get(self, json, keyName):
        if keyName == RTT:
            return self._getRTTs(json)
    
    def _getRTTs(self, json: dict) -> list:
        def preprocess(rtt: str):
            return int(float(rtt.replace("PT", "").replace("S", ""))*1000000)/1000

        roundtrips = json["roundtrips"]
        return [preprocess(roundtrip["rtt"]) for roundtrip in roundtrips]
    