from subprocess import run

class PSchedulerWrapper:
    def __init__(self, centralArchiverPath = "central_archiver.json"):
        self.program = "pscheduler"
        self.programOption = ""
        self.command = ""
        self.archiverOption = "--archiver"
        self.maxRunsOption = "--max-runs"
        self.repeatOption = "--repeat"
        self.outputFileOption = "--output"
        self.formatOption = "--format"
        self.options = []
        self.archiverPath = centralArchiverPath
        self.archiverConf = ""


    def MaxRuns(self, maxRuns: int) -> None:
        option = self.joinClauses(self.maxRunsOption, str(maxRuns), sep="=")
        self.addOption(option)
        return self
    
    def Repeat(self, interval: str) -> None:
        option = self.joinClauses(self.repeatOption, interval, sep="=")
        self.addOption(option)
        return self

    def Archiver(self) -> None:
        option = self.joinClauses(self.archiverOption, self.archiverConf)
        self.addOption(option)
        return self

    def OutputFile(self, path="", fileName=""):
        option = self.joinClauses(self.outputFileOption, path + fileName, sep="=")
        self.addOption(option)
        return self
    
    def Format(self, format):
        option = self.joinClauses(self.formatOption, format)
        self.addOption(option)
        return self

    def Command(self, command: str) -> None:
        self.command = command

    def ProgramOption(self, option):
        self.programOption = option

    def joinClauses(self, *args, sep = " ") -> str:
        if(isinstance(args[0], list)):
            return sep.join(args[0])
        return sep.join(args)

    def addOption(self, option) -> None:
        self.options.append(option)

    def __loadArchiverConf(self) -> None:
        with open(self.archiverPath, "r") as f:
            self.archiverConf = f.read()

    def run(self):
        run(self.command, shell=True)


class Task(PSchedulerWrapper):
    def __init__(self, centralArchiverPath = "central_archiver.json"):
        super().__init__(centralArchiverPath)
        self.ProgramOption("task")
        self.taskType = ""
        self.taskOptions = []
        self.sourceOption = "--source"
        self.destinationOption = "--dest"
        self.durationOption = "-t"
        self.intervalOption = "-i"
        self.LATENCY = "latency"
        self.RTT = "rtt"
        self.THROUGHPUT = "throughput"

    def TaskType(self, taskName):
        taskTypeNames = [self.LATENCY, self.RTT, self.THROUGHPUT]
        if taskName not in taskTypeNames:
            raise ValueError(f"{taskName} is not a valid name, choose one of {taskTypeNames}.")
        self.taskType = taskName
        return self

    def Source(self, sourceIp: str) -> None:
        option = self.joinClauses(self.sourceOption, sourceIp)
        self.addTaskOption(option)
        return self

    def Dest(self, destIp: str) -> None:
        option = self.joinClauses(self.destinationOption, destIp)
        self.addTaskOption(option)
        return self
    
    def Duration(self, duration):
        option = self.joinClauses(self.durationOption, duration)
        self.addOption(option)
        return self
    
    def Interval(self, interval):
        option = self.joinClauses(self.intervalOption, interval)
        self.addTaskOption(option)
        return self
    
    def addTaskOption(self, option):
        self.taskOptions.append(option)

    def mountCommand(self) -> str:
        options = self.joinClauses(self.options)
        taskOptions = self.joinClauses(self.taskOptions)
        self.Command(self.joinClauses(self.program, self.programOption, options, self.taskType, taskOptions))
        return self

    def getCommand(self):
        return self.command

class Throughput(Task):
    def __init__(self, centralArchiverPath = "central_archiver.json"):
        super().__init__(centralArchiverPath)
        self.TaskType(self.THROUGHPUT)
        self.durationOption = "--duration"

    def ThroughputDuration(self, duration: int) -> None:
        option = self.joinClauses(self.durationOption, str(duration))
        self.addTaskOption(option)
        return self

class Latency(Task):
    def __init__(self, centralArchiverPath = "central_archiver.json"):
        super().__init__(centralArchiverPath)
        self.TaskType(self.LATENCY)
        self.packetCountOption = "-c"
        self.packetIntervalOption = "-i"
        self.OUTPUT_RAW = "-R"
        
    def PacketCount(self, packetCount):
        option = self.joinClauses(self.packetCountOption, str(packetCount))
        self.addTaskOption(option)
        return self

    def PacketInterval(self, packetInterval):
        option = self.joinClauses(self.packetIntervalOption, packetInterval)
        self.addTaskOption(option)
        return self
    
    def OutputRaw(self):
        self.addTaskOption(self.OUTPUT_RAW)
        return self

class Rtt(Task):
    def __init__(self, centralArchiverPath = "central_archiver.json"):
        super().__init__(centralArchiverPath)
        self.TaskType(self.RTT)
        self.countOption = "--count"

    def Count(self, count: int) -> None:
        option = self.joinClauses(self.countOption, str(count))
        self.addTaskOption(option)
        return self