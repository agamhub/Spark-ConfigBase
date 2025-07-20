import psycopg2

conn_params = {
    'dbname': 'ifrs17',
    'user': 'postgres',
    'password': 'admin',
    # 'host': 'host.docker.internal',  # Change to your database host
    'host': 'localhost',  # Use service name for Docker Compose
    'port': '5432',
    # 'sslmode': 'verify-full' 
    # 'sslrootcert': '/app/cert/ca.crt',  
    # 'sslcert': '/app/cert/server.crt', 
    # 'sslkey': '/app/cert/server.key'  
}

def get_data(batchdate=None):
    """Fetch data from the PostgreSQL database as list of dicts, optionally filtered by batchdate."""
    try:
        conn = psycopg2.connect(**conn_params)
        cur = conn.cursor()
        if batchdate:
            cur.execute(
                "SELECT * FROM etl.spark_datamovement_summary WHERE batchdate = %s ORDER BY status, enddate DESC;",
                (batchdate,)
            )
        else:
            cur.execute(
                "SELECT * FROM etl.spark_datamovement_summary where 1=0;"
            )
        columns = [desc[0] for desc in cur.description]
        records = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(zip(columns, row)) for row in records]
    except psycopg2.Error as e:
        print(f"Error fetching data: {e}")
        return []
    finally:
        if 'conn' in locals() and conn:
            conn.close()

# if __name__ == "__main__":
#     data = get_data()
#     for row in data:
#         print(row)