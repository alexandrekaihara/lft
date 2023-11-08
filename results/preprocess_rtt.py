from json import load
from results.preprocess import Preprocess

class Latency(Preprocess):
    def getRTTs(self, json: dict) -> list:
        def preprocess(rtt: str):
            return float(rtt.replace("PT", "").replace("S", ""))

        rtts = json["rtt"]
        return [preprocess(rtt) for rtt in rtts]
    