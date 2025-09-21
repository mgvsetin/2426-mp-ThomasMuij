import sqlite3

with sqlite3.connect('test.sqlite') as conn:
  cur = conn.cursor()
  # cur.execute('CREATE TABLE usr ("name" VARCHAR(10) NOT NULL, age INTEGER)')
  cur.execute('SELECT * FROM usr')
  print(cur.fetchall())
cur.close()
# conn.close()

# conn = sqlite3.connect('test.sqlite')
cur = conn.cursor()
cur.execute('SELECT * FROM usr')
print(cur.fetchall())