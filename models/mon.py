from itertools import accumulate
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

def to_mon(id, forms, name):
    return Mon(id=id, forms=forms, name=name)

'''
To the serialized format
'''

def package_form_lists(mon_list):
    form_index_list = []
    form_count_list = []
    for mon in mon_list:
        form_count_list.append([
           mon.name, len(mon.forms)
        ])
        form_index_list += (
            package_mon_form_index(mon)
        ) 
    return (
        form_index_list,
        form_count_list
    )

def package_mon_form_index(mon):
    def package_form(form):
        return [
            form.form_id,
            form.type_combo,
            form.game_group,
            form.mon_id
        ]
    return [
        item
        for form in mon.forms
        for item in package_form(form)
    ]

# Number of fields in one form
FORM_CHUNK = len(
    package_mon_form_index(Mon(
        name='', id=-1, forms=[Form(
            name='', form_id=-1, mon_id=-1,
            type_combo=-1, game_group=-1,
        )]
    ))
)

'''
From the serialized format
'''

def unpackage_mon_list(
    form_count_list, form_index_list,
    extra_form_name_dict
):
    names = [m[0] for m in form_count_list]
    ends = list(accumulate([
        m[1] for m in form_count_list
    ]))
    pairs = [
        (i0*FORM_CHUNK, i1*FORM_CHUNK)
        for i0,i1 in zip([0]+ends, ends)
    ]
    for name,pair in zip(names, pairs):
        forms = form_index_list[slice(*pair)]
        yield unpackage_mon(
            name, forms, extra_form_name_dict
        )

def unpackage_mon(name, package, extra_form_name_dict):
    # Starting indices of each chunk
    starts = list(range(0, len(package), FORM_CHUNK))
    chunks = zip(starts, starts[1:]+[None])
    forms = [
        unpackage_form(
            package[slice(*pair)],
            extra_form_name_dict, name
        )
        for pair in chunks
    ]
    id = forms[0].form_id
    return Mon(
        forms=forms, id=id, name=name
    )

def unpackage_form(array, extra_form_name_dict, name):
    return Form(
        form_id=array[0],
        mon_id=array[3],
        type_combo=array[1],
        game_group=array[2],
        name=extra_form_name_dict.get(array[0], name)
    )

