import math

from base import utils
from base.design import design, ACTIVE
from tech import drc


def calculate_num_contacts(design_obj: design, tx_width, return_sample=False):
    """
    Calculates the possible number of source/drain contacts in a finger.
    """
    from base import contact
    num_contacts = int(math.ceil(tx_width / (design_obj.contact_width + design_obj.contact_spacing)))
    while num_contacts > 1:
        contact_array = contact.contact(layer_stack=("active", "contact", "metal1"),
                                        dimensions=[1, num_contacts],
                                        implant_type=None,
                                        well_type=None)
        if (contact_array.first_layer_height < tx_width and
                contact_array.second_layer_height < tx_width):
            if return_sample:
                return contact_array
            break
        num_contacts -= 1
    if num_contacts == 1 and return_sample:
        return contact.well
    return num_contacts


def calculate_contact_width(design_obj: design, width, well_contact_active_height):
    body_contact = calculate_num_contacts(design_obj, width - design_obj.contact_pitch,
                                          return_sample=True)

    contact_extent = body_contact.first_layer_height

    min_active_area = drc.get("minarea_cont_active_thin", design_obj.get_min_area(ACTIVE))
    min_active_width = utils.ceil(min_active_area / well_contact_active_height)
    active_width = max(contact_extent, min_active_width)

    # prevent minimum spacing drc
    active_width = max(active_width, width)
    return active_width, body_contact
