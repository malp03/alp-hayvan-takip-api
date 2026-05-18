from database import engine, Base, ensure_postgres_security, ensure_sqlite_schema
import models

def init_db():
    _ = models.Hayvan
    print("Veritabanı tabloları oluşturuluyor...")
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_schema()
    ensure_postgres_security()
    print("Veritabanı hazır!")

if __name__ == "__main__":
    init_db()
