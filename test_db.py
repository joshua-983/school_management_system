# test_db.py
import MySQLdb
from decouple import config

try:
    connection = MySQLdb.connect(
        host=config('DB_HOST', default='localhost'),
        user=config('DB_USER', default='root'),
        password=config('DB_PASSWORD', default=''),
        database=config('DB_NAME', default='school_db'),
        port=int(config('DB_PORT', default='3306'))
    )
    print("✅ MySQL connection successful!")
    connection.close()
except Exception as e:
    print(f"❌ MySQL connection failed: {e}")
