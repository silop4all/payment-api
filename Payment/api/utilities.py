# -*- coding: utf-8 -*-

import json
import ast
from traceback import print_exc
import collections

def isJson(object):
    """
    Check if the input is JSON object

    Returns True if input is JSON. Otherwise, it returns False.
    """
    try:
        json.loads(object)
    except: 
        return False
    return True


def object2dict(object, filter_data=True):
    """Convert a Paypal object to a dictionary
    """
    try:
        if filter_data == True:
            return ast.literal_eval(str(object.__data__))
        return ast.literal_eval(str(object))
    except:
        print_exc()
        return False


def unicodeDict2dict(data):
    if isinstance(data, basestring):
        return str(data)
    elif isinstance(data, collections.Mapping):
        return dict(map(convert, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(convert, data))
    else:
        return data



