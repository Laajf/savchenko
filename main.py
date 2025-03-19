from fastapi import FastAPI, Request, Depends, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import Session, User, Problem, Solution, pwd_context, engine
from sqlalchemy.orm import Session as DBSession
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from typing import Annotated
import json
import os
import uuid
from datetime import datetime
from urllib.parse import unquote

app = FastAPI(middleware=[
    Middleware(SessionMiddleware, secret_key="your-secret-key-32-chars-long")
])

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def format_datetime(value, format="%d.%m.%Y %H:%M"):
    return value.strftime(format) if value else ""


templates.env.filters["datetime"] = format_datetime
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(request: Request, db: DBSession = Depends(get_db)):
    user_id = request.session.get("user_id")
    return db.query(User).get(user_id) if user_id else None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: DBSession = Depends(get_db)):
    user = await get_current_user(request, db)
    problems = db.query(Problem).order_by(Problem.grade, Problem.chapter, Problem.number).all()

    problem_map = {}
    for p in problems:
        if p.grade not in problem_map:
            problem_map[p.grade] = {}
        if p.chapter not in problem_map[p.grade]:
            problem_map[p.grade][p.chapter] = []
        problem_map[p.grade][p.chapter].append(p.number)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "problems": problem_map,
        "user": user
    })


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
async def register(
        request: Request,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
        db: DBSession = Depends(get_db)
):
    try:
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="Username already exists")

        user = User(
            username=username,
            password_hash=pwd_context.hash(password)
        )
        db.add(user)
        db.commit()
        return RedirectResponse("/login", status_code=303)

    except Exception as e:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": str(e)
        })


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
        request: Request,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
        db: DBSession = Depends(get_db)
):
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user or not pwd_context.verify(password, user.password_hash):
            raise HTTPException(status_code=400, detail="Invalid credentials")

        request.session["user_id"] = user.id
        return RedirectResponse("/", status_code=303)

    except Exception as e:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": str(e)
        })


@app.get("/logout")
async def logout(request: Request):
    response = RedirectResponse("/")
    request.session.clear()
    return response


@app.get("/problem/{problem_id}", response_class=HTMLResponse)
async def problem(
        request: Request,
        problem_id: str,
        db: DBSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    try:
        if problem_id.count("-") != 2:
            return RedirectResponse("/")

        grade, chapter, number = problem_id.split("-")
        chapter = unquote(chapter.replace("_", " "))

        problem = db.query(Problem).filter(
            Problem.grade == grade,
            Problem.chapter == chapter,
            Problem.number == number
        ).first()

        if not problem:
            return RedirectResponse("/")

        solutions = db.query(Solution).filter(Solution.problem_id == problem.id).all()
        solution_data = []
        for s in solutions:
            solution_data.append({
                "id": s.id,
                "images": json.loads(s.images),
                "created_at": s.created_at,
                "author": s.author
            })

        return templates.TemplateResponse("problem.html", {
            "request": request,
            "problem": problem,
            "solutions": solution_data,
            "user": user
        })
    except Exception as e:
        print(f"Error: {e}")
        return RedirectResponse("/")


@app.get("/add-problem", response_class=HTMLResponse)
async def add_problem_form(
        request: Request,
        grade: str = None,
        chapter: str = None,
        db: DBSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("add_problem.html", {
        "request": request,
        "grade": grade,
        "chapter": chapter
    })


@app.post("/add-problem")
async def add_problem(
        request: Request,
        grade: str = Form(...),
        chapter: str = Form(...),
        number: str = Form(...),
        db: DBSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    try:
        if not user:
            return RedirectResponse("/login")

        chapter = chapter.strip()
        existing = db.query(Problem).filter(
            Problem.grade == grade,
            Problem.chapter == chapter,
            Problem.number == number
        ).first()

        if existing:
            problem_id = f"{grade}-{chapter.replace(' ', '_')}-{number}"
            return RedirectResponse(f"/problem/{problem_id}", status_code=303)

        problem = Problem(
            grade=grade,
            chapter=chapter,
            number=number
        )
        db.add(problem)
        db.commit()

        problem_id = f"{grade}-{chapter.replace(' ', '_')}-{number}"
        return RedirectResponse(f"/problem/{problem_id}/add", status_code=303)

    except Exception as e:
        return templates.TemplateResponse("add_problem.html", {
            "request": request,
            "error": str(e),
            "grade": grade,
            "chapter": chapter
        })


@app.get("/problem/{problem_id}/add", response_class=HTMLResponse)
async def add_solution_page(
        request: Request,
        problem_id: str,
        db: DBSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("add_solution.html", {
        "request": request,
        "problem_id": problem_id
    })


@app.post("/problem/{problem_id}/add")
async def add_solution(
        request: Request,
        problem_id: str,
        files: list[UploadFile] = File(...),
        db: DBSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    try:
        if not user:
            return RedirectResponse("/login")

        grade, chapter, number = problem_id.split("-")
        chapter = unquote(chapter.replace("_", " "))
        problem = db.query(Problem).filter(
            Problem.grade == grade,
            Problem.chapter == chapter,
            Problem.number == number
        ).first()

        if not problem:
            return RedirectResponse("/")

        image_paths = []
        for file in files:
            if not file.content_type.startswith("image/"):
                continue
            ext = file.filename.split('.')[-1]
            filename = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(await file.read())
            image_paths.append(f"/static/uploads/{filename}")

        solution = Solution(
            images=json.dumps(image_paths),
            user_id=user.id,
            problem_id=problem.id
        )
        db.add(solution)
        db.commit()
        return RedirectResponse(f"/problem/{problem_id}", status_code=303)

    except Exception as e:
        return templates.TemplateResponse("add_solution.html", {
            "request": request,
            "error": str(e),
            "problem_id": problem_id
        })


@app.post("/delete-solution/{solution_id}")
async def delete_solution(
        request: Request,
        solution_id: int,
        db: DBSession = Depends(get_db),
        user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")

    solution = db.query(Solution).filter(
        Solution.id == solution_id,
        Solution.user_id == user.id
    ).first()

    if solution:
        try:
            for img_path in json.loads(solution.images):
                full_path = os.path.join("static", img_path.lstrip("/static/"))
                if os.path.exists(full_path):
                    os.remove(full_path)
        except Exception as e:
            print(f"Error deleting images: {e}")

        db.delete(solution)
        db.commit()

    return RedirectResponse(request.headers.get('referer', '/'))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)