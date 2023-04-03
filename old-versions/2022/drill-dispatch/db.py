import enum
from sqlalchemy import Column, Enum, Integer, String, Text, DateTime, LargeBinary, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

Base = declarative_base()
    
class Run(Base):
    __tablename__ = 'run'
    
    id = Column(Integer, primary_key=True)
    started = Column(DateTime())
    ended = Column(DateTime(), nullable=True)
    notes = Column(Text(), nullable=True)
    depth_start = Column(Float(), nullable=True)
    depth_end = Column(Float(), nullable=True)
    

class RawPacket(Base):
    __tablename__ = 'raw_packet'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime())
    data = Column(LargeBinary())

class DisplayReading(Base):
    __tablename__ = 'display_reading'

    id = Column(Integer, primary_key=True)
    display_id = Column(Enum('load_cell', 'depth_encoder'))
    timestamp = Column(DateTime())
    reading = Column(Float())

    
engine = create_engine('sqlite:///drill.db')
Session = sessionmaker(bind=engine)

if __name__ == '__main__':
    answer = raw_input("Create a new database file? (y/n) ")

    if (answer.rstrip() == 'y'):
        print "creating"
        Base.metadata.create_all(engine)
    
