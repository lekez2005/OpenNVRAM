.PARAM PERIOD=800ps
.PARAM PERIOD={PERIOD}
Vdd vdd gnd {vdd_value}
Vin a gnd pulse 0 {vdd_value} 0ps 20ps 20ps '0.5*PERIOD' 'PERIOD'
X1 a out_bar out vdd gnd        {buffer_name}    *

.meas tran rise_time TRIG V(a) val='{half_vdd}' FALL=1 TD={meas_delay} TARG V(out_bar) val='{half_vdd}' RISE=1 TD={meas_delay}
.meas tran fall_time TRIG V(a) val='{half_vdd}' RISE=1 TD={meas_delay} TARG V(out_bar) val='{half_vdd}' FALL=1 TD={meas_delay}

simulator lang=spectre
dcOp dc write="spectre.dc" readns="spectre.dc" maxiters=150 maxsteps=10000 annotate=status
tran tran stop=1.1n annotate=status maxiters=5
saveOptions options save=lvlpub nestlvl=1 pwr=total
simulatorOptions options temp={TEMPERATURE} maxnotes=10 maxwarns=10  preservenode=all topcheck=fixall dc_pivot_check=yes
