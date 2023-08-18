class Utils:

    @classmethod
    def get_element_states(cls, ctx, ids_to_find):
        ret_val = {}
        for el_group in ctx:
            if type(el_group) == list:
                for el in el_group:
                    if el['id']['idx'] in ids_to_find:
                        ret_val[el['id']['idx']] = el['value']

        return ret_val
