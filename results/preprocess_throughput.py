from json import load
from results.preprocess import Preprocess
from experiment.constants import *


class Throughput(Preprocess):
    def get(self, json, keyName):
        if keyName == THROUGHPUT:
            return self._getThroughputs(json)
    
    def _getThroughputs(self, json: dict) -> list:
        intervals = json['intervals']
        return [intervals[i]["streams"][0]["throughput-bits"]/10**6 for i in range(len(intervals)-1)]