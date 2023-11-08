from json import load

class Preprocess:
    def readJson(self, path: str):
        with open(path, "r") as f:
            json = load(f)
        return json