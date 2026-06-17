import os
import shutil
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

def _app_data_dir():
    appdata = os.getenv("APPDATA")
    if not appdata:
        appdata = os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    data_dir = os.path.join(appdata, "ALP Ziraat", "HayvanTakip")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _legacy_database_paths(db_name):
    candidates = [
        os.path.abspath(db_name),
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), db_name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), db_name),
    ]
    unique_paths = []
    for path in candidates:
        if path not in unique_paths:
            unique_paths.append(path)
    return unique_paths


def _default_sqlite_url():
    db_name = "alp_veri.db"
    db_path = os.path.join(_app_data_dir(), db_name)
    if not os.path.exists(db_path):
        for legacy_path in _legacy_database_paths(db_name):
            if os.path.abspath(legacy_path) == os.path.abspath(db_path):
                continue
            if os.path.exists(legacy_path):
                shutil.copy2(legacy_path, db_path)
                break
    return "sqlite:///" + db_path.replace("\\", "/")


def _normalize_database_url(url):
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


# Kullanıcı veritabanı bağlantı adresini (URL) çevresel değişkenden alabilir.
# Yoksa varsayılan olarak kullanıcı veri klasöründeki SQLite veritabanı kullanılır.
SQLALCHEMY_DATABASE_URL = _normalize_database_url(os.getenv(
    "DATABASE_URL", 
    _default_sqlite_url()
))

# PostgreSQL (örneğin Supabase vb.) kullanıldığında pool ayarları değişebilir
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    connect_args = {}
    # Supabase pooler/PgBouncer transaction mode does not support driver-level
    # prepared statements reliably; psycopg can otherwise crash on deploy with
    # "prepared statement ... already exists".
    connect_args["prepare_threshold"] = None
    if "supabase.com" in SQLALCHEMY_DATABASE_URL and "sslmode=" not in SQLALCHEMY_DATABASE_URL:
        connect_args["sslmode"] = "require"
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def ensure_sqlite_schema():
    if not SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as connection:
        def table_exists(table):
            return bool(connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchall())

        def columns_for(table):
            return {
                row[1]
                for row in connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            }

        if table_exists("hayvanlar"):
            columns = columns_for("hayvanlar")
            if "veri_json" not in columns:
                connection.exec_driver_sql("ALTER TABLE hayvanlar ADD COLUMN veri_json TEXT")
            if "ciftlik_id" not in columns:
                connection.exec_driver_sql("ALTER TABLE hayvanlar ADD COLUMN ciftlik_id VARCHAR")

        if table_exists("islem_gecmisi"):
            columns = columns_for("islem_gecmisi")
            for column in (
                "islem_tipi",
                "kullanici_id",
                "kullanici_adi",
                "rol",
                "ciftlik_id",
                "hedef_tipi",
                "hedef_id",
            ):
                if column not in columns:
                    connection.exec_driver_sql(f"ALTER TABLE islem_gecmisi ADD COLUMN {column} VARCHAR")


def ensure_postgres_security():
    pass


def ensure_postgres_schema_updates():
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
