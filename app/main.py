import random
import string
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import URL
from app.schemas import URLCreate, URLResponse, URLStats
from app.cache import get_cached_url, set_cached_url


def generate_short_code(length: int = 6) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="URL Shortener",
    description="A containerised URL shortener — Project 1",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/shorten", response_model=URLResponse, status_code=201)
def shorten_url(payload: URLCreate, db: Session = Depends(get_db)):
    original_url = str(payload.url)

    existing = db.query(URL).filter(URL.original_url == original_url).first()
    if existing:
        return URLResponse(
            short_code=existing.short_code,
            short_url=f"http://localhost:8000/{existing.short_code}",
            original_url=existing.original_url,
        )

    for _ in range(5):
        code = generate_short_code()
        if not db.query(URL).filter(URL.short_code == code).first():
            break
    else:
        raise HTTPException(status_code=500, detail="Could not generate unique code")

    url_entry = URL(original_url=original_url, short_code=code)
    db.add(url_entry)
    db.commit()
    db.refresh(url_entry)

    set_cached_url(code, original_url)

    return URLResponse(
        short_code=url_entry.short_code,
        short_url=f"http://localhost:8000/{url_entry.short_code}",
        original_url=url_entry.original_url,
    )


@app.get("/stats/{short_code}", response_model=URLStats)
def get_stats(short_code: str, db: Session = Depends(get_db)):
    url_entry = db.query(URL).filter(URL.short_code == short_code).first()
    if not url_entry:
        raise HTTPException(status_code=404, detail="Short code not found")
    return url_entry


@app.get("/{short_code}")
def redirect_url(short_code: str, db: Session = Depends(get_db)):
    cached = get_cached_url(short_code)
    if cached:
        db.query(URL).filter(URL.short_code == short_code).update(
            {"clicks": URL.clicks + 1}
        )
        db.commit()
        return RedirectResponse(url=cached, status_code=307)

    url_entry = db.query(URL).filter(URL.short_code == short_code).first()
    if not url_entry:
        raise HTTPException(status_code=404, detail="Short code not found")

    url_entry.clicks += 1
    db.commit()

    set_cached_url(short_code, url_entry.original_url)

    return RedirectResponse(url=url_entry.original_url, status_code=307)