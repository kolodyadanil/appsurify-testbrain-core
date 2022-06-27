import typing
import hashlib


def hash_list_values(lst: typing.List[str]) -> typing.List[str]:
    if isinstance(lst, (list, tuple)):
        return [hashlib.md5(i.encode('utf-8')).hexdigest() for i in lst]
    return []
