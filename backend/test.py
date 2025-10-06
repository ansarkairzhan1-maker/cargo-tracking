from sqlalchemy import create_engine
engine = create_engine("mysql+pymysql://freedb_kazkans:H4Dba3Eqb3jY@W8@sql.freedb.tech:3306/freedb_cargotest")
conn = engine.connect()
print("SQLAlchemy Connected!")
conn.close()