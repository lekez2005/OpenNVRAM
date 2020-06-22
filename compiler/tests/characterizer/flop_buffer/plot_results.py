import numpy as np
import matplotlib.pyplot as plt


results = {
    "single_stage_2": "single--2",
    "single_stage_3": "single--3",
    # "double_stage_1": "double_1--",
    "double_stage_2": "double_2--"
}


def plot_data(data_, label, print_label, ):
    sizes = data_[:, 1]
    delays = data_[:, 2] * 1e12

    plt.plot(sizes, delays, label=label)

    arg_min = np.argmin(delays)
    print("{:>15}:\t {:5.3g} {:10.4g}".format(print_label, sizes[arg_min],
                                              delays[arg_min]))


for result in results:
    data = np.loadtxt(result+".csv", delimiter=",")
    if data[0][0] == 0.0:  # single stage
        plot_data(data, results[result], result)
    else:
        grouped = {}
        for row in data:
            stage_1 = row[0]
            if stage_1 not in grouped:
                grouped[stage_1] = []
            grouped[stage_1].append([stage_1, row[1], row[2]])
        for stage_1 in grouped:
            stage_1_data = np.array(grouped[stage_1])
            label = "{}{:g}".format(results[result], stage_1)
            plot_data(stage_1_data, label, label)

plt.xlabel("size")
plt.ylabel("Delay (ps)")
plt.legend()
plt.show()
