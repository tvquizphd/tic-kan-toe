from pydantic import BaseModel
from typing import Dict, List
from typing import Optional
import json

class Form(BaseModel):
    game_group: int
    type_combo: int
    form_id: int
    mon_id: int
    name: str

class Mon(BaseModel):
    forms: List[Form]
    name: str
    id: int

def to_form(name, form_id, type_combo, game_group, mon_id):
    return Form(
        name=name,
        form_id=form_id,
        type_combo=type_combo,
        game_group=game_group,
        mon_id=mon_id
    )

# TODO
def to_mon(id, forms, name):
    return Mon(id=id, forms=forms, name=name)


# JSON-friendly format 
def package_mon(mon):
    def package_form(form):
        # chunk = 4
        return [
            form.form_id,
            form.type_combo,
            form.game_group,
            form.mon_id
        ]
    # prefix = 1
    blocks = [
       [mon.name]
    ] + [
        package_form(form)
        for form in mon.forms
    ]
    return [
        item for block in blocks
        for item in block
    ]

def unpackage_form(array, extra_form_name_dict, name):
    return Form(
        form_id=array[0],
        mon_id=array[3],
        type_combo=array[1],
        game_group=array[2],
        name=extra_form_name_dict.get(array[0], name)
    )

def unpackage_mon(package, extra_form_name_dict):
    prefix, chunk = 1, 4
    (name,) = package[:prefix]
    # Starting indices of each chunk
    starts = list(range(
        prefix, len(package)-prefix, chunk
    ))
    chunks = zip(starts, starts[1:]+[None])
    forms = [
        unpackage_form(
            package[slice(*pair)], extra_form_name_dict, name
        )
        for pair in chunks
    ]
    id = forms[0].form_id
    return Mon(
        forms=forms, id=id, name=name
    )
