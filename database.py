from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from passlib.context import CryptContext
from datetime import datetime
import os

Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    solutions = relationship("Solution", back_populates="author")

class Problem(Base):
    __tablename__ = "problems"
    id = Column(Integer, primary_key=True)
    grade = Column(String(10), nullable=False)
    chapter = Column(String(100), nullable=False)
    number = Column(String(20), nullable=False)
    solutions = relationship("Solution", back_populates="problem")

class Solution(Base):
    __tablename__ = "solutions"
    id = Column(Integer, primary_key=True)
    images = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    problem_id = Column(Integer, ForeignKey("problems.id"), nullable=False)
    author = relationship("User", back_populates="solutions")
    problem = relationship("Problem", back_populates="solutions")

# Путь к базе данных
db_path = os.path.join(os.path.dirname(__file__), "database.db")

# Создаем файл базы данных, если его нет
if not os.path.exists(db_path):
    print("Создаем новую базу данных...")
    open(db_path, "w").close()

# Подключение к базе данных
engine = create_engine(f"sqlite:///{db_path}")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def init_db():
    db = Session()
    try:
        # Добавляем начальные данные, если их нет
        if not db.query(Problem).first():
            problem = Problem(
                grade="Савченко 3е издание",
                chapter="Движение с постоянной скоростью",
                number="1"
            )
            db.add(problem)
            db.commit()
            print("✅ Начальные данные успешно добавлены")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        db.rollback()
    finally:
        db.close()

# Инициализация базы данных при импорте
init_db()