
rows = [{'a': 'a1', 'b': 'b1'},
        {'a': 'a2', 'b': 'b2'},
        {'b': 'b3', 'a': 'a3'}]

cols = list(rows[0].keys())
row_len = len(cols)
if any(len(row) != row_len for row in rows):
    raise ValueError("All rows must have the same number of columns")

placeholders_per_row = '(' + ', '.join(['%s'] * row_len) + ')'
placeholders = ', '.join([placeholders_per_row] * len(rows))
params = [row.get(col) for row in rows for col in cols]

print(placeholders)
print(params)

print(f"""
    INSERT INTO table
    ({', '.join(cols)})
    VALUES {placeholders}
    """)