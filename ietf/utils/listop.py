import operator

def orl(list):
    """ Return the "or" of every element in a list.
    Used to generate "or" queries with a list of Q objects. """
    return reduce(operator.__or__, list)

def flattenl(list):
    """ Flatten a list one level, e.g., turn
	[ ['a'], ['b'], ['c', 'd'] ] into
	[ 'a', 'b', 'c', 'd' ]
    """
    return reduce(operator.__concat__, list)
