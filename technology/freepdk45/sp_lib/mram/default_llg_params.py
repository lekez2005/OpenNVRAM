import math

def sech(x_):
    return 2 / (math.exp(x_) + math.exp(-x_))

sot_R = "560"

alpha = "0.07"
# alpha = "0.09"
c_ferro = "0.1"
v_pol = "1"
Fm_Lx = 45e-9
Fm_Ly = 45e-9
Fm_Lz = "0.7n"
H_ext = "0.01"
Ku = "9e5"
Ms = "1185000"
Nxx = "-0.0242"
Nyy = "-0.0242"
Nzz = "-0.951"
TI_Lx = "45n"
TI_Lz = 5e-9

diffusion_length = 3.5e-9
spin_hall_angle = 0.7316
spin_hall_angle_effective = spin_hall_angle * (1 - sech(TI_Lz / diffusion_length))
shunt_factor = 0.7311827956989247

g_AD = spin_hall_angle_effective * shunt_factor
g_FL = "0.5*g_AD"

fm_temperature = "0"
ra_product = 5e-12
Rp = ra_product / (Fm_Lx*Fm_Ly)
spin_pol = "1.357"
spin_wave = "8.9e-5"
tmr_v0 = "0.5"

llg_prescale = 0.001

# sotfet
reference_vt = 1
ferro_ratio = 0.1
