from pg_connection import get_connection
from psycopg import sql

class Query:

    @staticmethod
    def sanitize_identifiers(table: str, columns: list[str]):
        table = sql.Identifier(table)
        columns = [sql.Identifier(column) for column in columns]
        values_placeholders = sql.SQL(', ').join(sql.Placeholder() * len(columns))

        return table, columns, values_placeholders

    @staticmethod
    def insert(table: str, columns: list[str], row: list[str]):
        table, columns, values_placeholders = Query.sanitize_identifiers(table, columns)

        query = sql.SQL('INSERT INTO {table} ({columns}) VALUES ({values})').format(
                    table=table,
                    columns=columns,
                    values=values_placeholders)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(row))

    @staticmethod
    def select(table: str, columns: list[str]):
        table, columns, values_placeholders = Query.sanitize_identifiers(table, columns)

        query = sql.SQL('SELECT {columns} FROM {table}').format(
                    table=table,
                    columns=columns,)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)

    @staticmethod
    def select_order_by()