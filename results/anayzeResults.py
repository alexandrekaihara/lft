import matplotlib.pyplot as plt
from results.preprocess_throughput import Throughput
from scipy import stats
import numpy as np


def confidence_interval(data, confidence=0.95):
    mean = np.mean(data)
    stderr = stats.sem(data)
    margin_of_error = stderr * stats.t.ppf((1 + confidence) / 2.0, len(data) - 1)
    lower_bound = mean - margin_of_error
    upper_bound = mean + margin_of_error
    return lower_bound, mean, upper_bound


t = Throughput()
t1 = t.readJson("results/data/wired_emu_emu_throughput_1.json")
t2 = t.readJson("results/data/wired_emu_emu_throughput_2.json")
t3 = t.readJson("results/data/wired_emu_emu_throughput_3.json")

throughput_data_1 = t.getThroughputs(t1)
throughput_data_2 = t.getThroughputs(t2)
throughput_data_3 = t.getThroughputs(t3)

plt.plot(throughput_data_1, label='Arary 1')
plt.plot(throughput_data_2, label='Arary 2')
plt.plot(throughput_data_3, label='Arary 3')
plt.title('Throughput Data')
plt.xlabel('Time')
plt.ylabel('Throughput')
plt.show()


c1 = confidence_interval(throughput_data_1)
c2 = confidence_interval(throughput_data_2)
c3 = confidence_interval(throughput_data_3)

plt.plot(c1, (0, 0),'ro-',color='orange')
plt.plot(c2, (1, 1),'ro-',color='orange')
plt.plot(c3, (2, 2),'ro-',color='orange')

plt.xlabel('Confidence Intervals')
plt.ylabel('Mean')
plt.title('Three Confidence Intervals')

plt.yticks(range(len(3)), ['CI 1', 'CI 2', 'CI 3'])

plt.show()