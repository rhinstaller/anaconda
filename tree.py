def build_tree (x):
    if (x == ()): return ()
    if (len (x) == 1): return (x[0],)
    else: return (x[0], build_tree (x[1:]))

def merge (a, b):
    if a == (): return build_tree (b)
    if b == (): return a
    if b[0] == a[0]:
        if len (a) > 1 and isinstance (a[1], type (())):
            return (a[0],) + (merge (a[1], b[1:]),) + a[2:]
        elif b[1:] == (): return a
        else: return (a[0],) + (build_tree (b[1:]),) + a[1:]
    else:
        return (a[0],) + merge (a[1:], b)

