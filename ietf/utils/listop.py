# Copyright The IETF Trust 2007, All Rights Reserved

import operator

def orl(list):
    """ Return the "or" of every element in a list.
    Used to generate "or" queries with a list of Q objects. """
    if list:
        return reduce(operator.__or__, list)
    else:
        return None
        
def flattenl(list):
    """ Flatten a list one level, e.g., turn
	[ ['a'], ['b'], ['c', 'd'] ] into
	[ 'a', 'b', 'c', 'd' ]
    """
    if list:
        return reduce(operator.__concat__, list)
    else:
        return []