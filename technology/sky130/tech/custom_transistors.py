"""
Placeholder implementation of support for custom transistors
"""
from base.design import design, ACTIVE, TAP_ACTIVE
from base.layout_clearances import extract_unique_rects
from base.vector import vector
from globals import OPTS
from pgates.ptx import ptx

HIGH_VOLTAGE = "hvl"
NOMINAL = "nominal"
from tech import spice, drc, parameter

mode = NOMINAL

HVI = "hvi"
HVNTM = "hvntm"


def set_nominal():
    global mode
    mode = NOMINAL
    parameter["min_tx_size"] = 0.36
    parameter["beta"] = 2.5

    drc["minwidth_poly"] = 0.15
    drc["well_extend_active"] = 0.18
    drc["well_enclosure_active"] = 0.18
    drc["active_to_body_active"] = 0.27
    drc["active_to_active"] = 0.27

    spice["nmos"] = "sky130_fd_pr__nfet_01v8"
    spice["pmos"] = "sky130_fd_pr__pfet_01v8"
    spice["minwidth_tx_pmos"] = 0.42

    set_derived()


def set_high_voltage():
    global mode
    mode = HIGH_VOLTAGE

    parameter["min_tx_size"] = 0.42
    parameter["beta"] = 2

    drc["minwidth_poly"] = 0.5
    drc["well_extend_active"] = 0.18
    drc["well_enclosure_active"] = 0.33
    drc["active_to_body_active"] = 0.37
    drc["active_to_active"] = 0.37

    spice["nmos"] = "sky130_fd_pr__nfet_g5v0d10v5"
    spice["pmos"] = "sky130_fd_pr__pfet_g5v0d10v5"
    spice["minwidth_tx_pmos"] = 0.42

    set_derived()


def set_derived():
    drc["minwidth_tx"] = parameter["min_tx_size"]

    spice["minwidth_tx"] = drc["minwidth_tx"]
    spice["channel"] = drc["minlength_channel"]


def set_transistor_mode(voltage_mode=None):
    voltage_mode = voltage_mode or NOMINAL

    assert voltage_mode in [HIGH_VOLTAGE, NOMINAL]
    if voltage_mode == NOMINAL:
        set_nominal()
    elif voltage_mode == HIGH_VOLTAGE:
        set_high_voltage()
    else:
        assert False, f"Invalid transistor mode {mode}"


def add_voltage_layers(obj: design):
    set_nominal()
    if obj.__class__.__name__ == "LevelShifter":
        add_level_shifter_layers(obj)
        return
    elif obj.name.startswith("level_shifter_driver"):
        add_wordline_shifter_layers(obj)
        return
    voltage_mode = getattr(obj, "voltage_mode", None)

    if not voltage_mode == HIGH_VOLTAGE:
        return
    add_hvntm(obj)
    add_hvi(obj)


def add_enclosing_rect(obj, layer, rect, x_enclosure, y_enclosure=None):
    if y_enclosure is None:
        y_enclosure = x_enclosure
    min_width = obj.get_min_layer_width(layer)
    x_enclosure = max(x_enclosure, 0.5 * (min_width - rect.width))
    y_enclosure = max(y_enclosure, 0.5 * (min_width - rect.height))
    obj.add_rect(layer, offset=rect.ll() - vector(x_enclosure, y_enclosure),
                 width=rect.width + 2 * x_enclosure,
                 height=rect.height + 2 * y_enclosure)


def add_hvntm(obj: design):
    nmos_actives = ptx.get_mos_active(obj, tx_type="n", recursive=True)
    if not nmos_actives:
        return

    enclosure = drc.get("hvntm_enclose_active")
    for nmos_active in nmos_actives:
        add_enclosing_rect(obj, HVNTM, nmos_active, enclosure)


def expand_hvntm_downwards(obj: design):
    tap = obj.create_mod_from_str(OPTS.body_tap)
    bottom = - 0.5 * tap.height
    # hvntm, expand downwards to align bottom edges
    hvntm_rects = obj.get_layer_shapes(HVNTM, recursive=True)
    hvntm_rects = extract_unique_rects(hvntm_rects, min_space=0)
    hvntm_rects = list(sorted(hvntm_rects, key=lambda x: x.lx()))
    if not hvntm_rects:
        return
    if len(hvntm_rects) == 1:
        hvntm_rects = [hvntm_rects[0], hvntm_rects[0]]

    for left_rect, right_rect in zip(hvntm_rects[:-1], hvntm_rects[1:]):
        top = min(left_rect.uy(), right_rect.uy())
        x_offset = left_rect.lx()
        obj.add_rect(HVNTM, vector(x_offset, bottom),
                     width=right_rect.rx() - x_offset, height=top - bottom)


def add_hvi(obj: design):
    active_rects = (obj.get_layer_shapes(ACTIVE, recursive=True) +
                    obj.get_layer_shapes(TAP_ACTIVE, recursive=True))
    unique_rects = extract_unique_rects(active_rects, min_space=0)

    enclosure = drc.get("hvi_enclose_active")
    for active_rect in unique_rects:
        add_enclosing_rect(obj, HVI, active_rect, enclosure)

    hvi_space = obj.get_space(HVI)
    hvi_rects = obj.get_layer_shapes(HVI, recursive=False)
    unique_hvi = extract_unique_rects(hvi_rects, min_space=hvi_space)
    for hvi_rect in unique_hvi:
        obj.add_rect(HVI, offset=hvi_rect.ll(), width=hvi_rect.width,
                     height=hvi_rect.height)


def add_level_shifter_layers(obj: design):
    # hvi
    enclosure = drc.get("hvi_enclose_active")
    hvi_rect = obj.get_max_shape(HVI, "rx")
    top_tap = obj.get_max_shape(TAP_ACTIVE, "uy")
    bottom_tap = obj.get_max_shape(TAP_ACTIVE, "by")
    y_offset = bottom_tap.by() - enclosure
    y_top = top_tap.uy() + enclosure
    obj.add_rect(HVI, vector(hvi_rect.lx(), y_offset), height=y_top - y_offset,
                 width=hvi_rect.width)
    # hvntm
    expand_hvntm_downwards(obj)


def add_wordline_shifter_layers(obj: design):
    tap = obj.create_mod_from_str(OPTS.body_tap)
    bottom = - 0.5 * tap.height

    # hvi
    shifter_hvi = obj.get_max_shape(HVI, "lx", recursive=True)
    obj.add_rect(HVI, vector(shifter_hvi.lx(), bottom), height=obj.height - 2 * bottom,
                 width=obj.width - shifter_hvi.lx())

    expand_hvntm_downwards(obj)
