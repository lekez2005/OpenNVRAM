from characterizer.delay_params_base import RC, DelayParamsBase


class DelayParams(DelayParamsBase):
    # width, space, res, cap
    poly = [
        RC(0.05, 0.14, 7.8, 0.361),
    ]
    metal1 = [
        RC(0.065, 0.065, 0.38, 0.255),
        RC(0.08, 0.08, 0.38, 0.232),
    ]
    metal2 = [
        RC(0.07, 0.07, 0.25, 0.118),
        RC(0.08, 0.08, 0.25, 0.115),
    ]
    metal3 = [
        RC(0.07, 0.07, 0.25, 0.104),
        RC(0.08, 0.08, 0.25, 0.1),
    ]
    metal4 = [
        RC(0.14, 0.14, 0.21, 0.0814),
    ]
    metal5 = [
        RC(0.14, 0.14, 0.21, 0.0838),
    ]
    metal6 = [
        RC(0.14, 0.14, 0.21, 0.0999),
    ]
    metal7 = [
        RC(0.4, 0.4, 0.075, 0.186),
    ]
    metal8 = [
        RC(0.4, 0.4, 0.075, 0.559),
    ]
    metal9 = [
        RC(0.8, 0.8, 0.03, 1.52),
    ]
    metal10 = [
        RC(0.8, 0.8, 0.03, 2.02),
    ]
