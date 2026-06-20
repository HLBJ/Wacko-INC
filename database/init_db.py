from database.db import engine, Base
import database.models  # noqa

Base.metadata.create_all(bind=engine)

print("Database created")
