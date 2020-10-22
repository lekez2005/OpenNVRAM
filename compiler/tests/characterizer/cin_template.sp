simulator lang=spice
* Adapted from From Weste and Harris Circuit simulation chapter, Pg 309
* capdelay.hsp
* Extract effective gate capacitance for delay estimation.
*----------------------------------------------------------------------
* Parameters and models
*----------------------------------------------------------------------
* Simulation netlist
*----------------------------------------------------------------------
.PARAM PERIOD={PERIOD}
Vdd vdd gnd {vdd_value}
Vgnd gnd 0 0
Vin a gnd pulse 0 {vdd_value} 0ps 20ps 20ps '0.5*PERIOD' 'PERIOD'
X1 a b c vdd gnd        {in_buffer_name}    * set appropriate slope
X3 c d d_bar vdd gnd    {driver_name}       * drive real load

X6 c g g_bar vdd gnd    {driver_name}       * drive linear capacitor
cdelay g gnd 'Cload'                        * linear capacitor
{dut_instance}
{dummy_inst}
* instantiate real load (or add more spice), d is the input to the load

