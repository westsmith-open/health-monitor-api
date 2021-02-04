from sqlalchemy import Column, ForeignKey, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os
from time import sleep

Base = declarative_base()


class User(Base):
    __tablename__ = "user"
    username = Column(String, primary_key=True)
    hashed_password = Column(String)
    role = Column(Integer)
    expected_calories_per_day = Column(Integer)


class Calorie(Base):
    __tablename__ = "calorie"
    id = Column(Integer, primary_key=True)
    text = Column(String)
    number_of_calories = Column(Integer)
    username = Column(String, ForeignKey("user.username", ondelete="CASCADE"))
    date = Column(String)
    time = Column(String)
    below_expected = Column(Boolean)


sql_connect = "sqlite:///:memory:"  # Unit test only. For some reason this fails when handling real http requests.
# sql_connect = 'postgresql://postgres:mysecretpassword@localhost/template1'
if "DATABASE_URL" in os.environ:
    sql_connect = os.environ["DATABASE_URL"]
    sleep(2)  # Give external database time to accept connections

# engine = create_engine(sql_connect, echo=True)
engine = create_engine(sql_connect)
Base.metadata.create_all(engine)
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)


# For testing
def get_db_session():
    return DBSession()


# For testing
def recreate_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
