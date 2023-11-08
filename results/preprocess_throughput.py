from json import load
from results.preprocess import Preprocess


class Throughput(Preprocess):
    def getThroughputs(self, json: dict) -> list:
        intervals = json['intervals']
        return [intervals[i]["streams"][0]["throughput-bits"] for i in range(len(intervals)-1)]