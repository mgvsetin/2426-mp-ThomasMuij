a = set()
print(a)

a.update(['a', 'b', 'a'])
print(a)

a.update(['a', 'b', 'a', 'd'])
print(a)

b = set()
{b.update(item) for item in [['a', 'b', 'a'], ['a', 'b', 'a', 'd']]}
print(b)