from json import load
import numpy as np


class Preprocess:
    def readJson(self, path: str):
        with open(path, "r") as f:
            json = load(f)
        return json
    
    def remove_outliers(data):
        mean_value = np.mean(data)
        std_dev = np.std(data)

        threshold = 3 * std_dev

        filtered_data = [x for x in data if (mean_value - threshold) < x < (mean_value + threshold)]

        return filtered_data