# Validation Checklist: TestBoost Core

**Purpose**: Critères de validation détaillés pour chaque tâche d'implémentation
**Created**: 2025-11-23
**Feature**: [spec.md](./spec.md)

**Note**: Ce fichier contient les détails complets de validation. Pour les critères résumés, voir `tasks.md`.

---

## Test Projects

Trois projets Java Maven de référence pour valider les fonctionnalités TestBoost.

### Repositories

| ID | Taille | Repository | Caractéristiques |
|----|--------|------------|------------------|
| TP1 | Petit | `LableOrg/java-maven-junit-helloworld` | ~5 classes, JUnit basique |
| TP2 | Moyen | `spring-petclinic/spring-petclinic-reactjs` | ~50 classes, Spring Boot, React |
| TP3 | Gros | `spring-petclinic/spring-petclinic-microservices` | 8+ modules, Config Server, Docker |

### Setup Commands

```bash
# T005a - Clone all repositories
mkdir -p test-projects
git clone https://github.com/LableOrg/java-maven-junit-helloworld test-projects/java-maven-junit-helloworld
git clone https://github.com/spring-petclinic/spring-petclinic-reactjs test-projects/spring-petclinic-reactjs
git clone https://github.com/spring-petclinic/spring-petclinic-microservices test-projects/spring-petclinic-microservices

# T005b - Build small project
cd test-projects/java-maven-junit-helloworld && mvn clean verify

# T005c - Build medium project
cd test-projects/spring-petclinic-reactjs && mvn clean package -DskipTests

# T005d - Build large project
cd test-projects/spring-petclinic-microservices && mvn clean install -DskipTests

# T005e - Launch applications
# Petit: tests only
cd test-projects/java-maven-junit-helloworld && mvn test

# Moyen: Spring Boot
cd test-projects/spring-petclinic-reactjs && mvn spring-boot:run &
sleep 30 && curl -f http://localhost:8080/actuator/health

# Gros: Docker Compose
cd test-projects/spring-petclinic-microservices && docker-compose up -d
sleep 60 && docker-compose ps
```

---

## Phase 1: Setup Details

### CHK001 T001 - Project Structure

**Done when**:
1. Répertoire `src/` créé à la racine
2. Sous-répertoires présents :
   - `src/api/` - FastAPI routes et schemas
   - `src/cli/` - Typer commands
   - `src/core/` - Business logic
   - `src/db/` - SQLAlchemy models et migrations
   - `src/lib/` - Utilities (config, logging, llm)
   - `src/workflows/` - LangGraph workflows
   - `src/agents/` - DeepAgents adapters
   - `src/mcp_servers/` - MCP tool servers
3. Chaque répertoire contient `__init__.py`
4. Pas de fichiers temporaires ou cache

**Validation**:
```bash
# Vérifier structure
tree src -d -L 2

# Vérifier __init__.py
find src -type d -exec test -f {}/__init__.py \; -print | wc -l
# Devrait retourner 8+
```

### CHK002 T002 - Poetry Setup

**Done when**:
1. `pyproject.toml` contient :
   - `[tool.poetry]` avec name, version, description
   - `[tool.poetry.dependencies]` avec Python >=3.11
   - Dependencies : fastapi, uvicorn, sqlalchemy, alembic, typer, pydantic-settings, structlog, langgraph, mcp
2. `poetry.lock` généré
3. `.venv/` créé après `poetry install`

**Dependencies requises**:
```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.115"
uvicorn = "^0.32"
sqlalchemy = "^2.0"
alembic = "^1.14"
typer = "^0.13"
pydantic-settings = "^2.6"
structlog = "^24.4"
langgraph = "^0.2"
langchain-openai = "^0.2"
langchain-anthropic = "^0.3"
mcp = "^1.1"
httpx = "^0.27"
```

### CHK003 T003 - Linting Configuration

**Done when**:
```toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP"]

[tool.black]
line-length = 100
target-version = ["py311"]
```

### CHK004 T004 - Environment Variables

**Done when** `.env.example` contient :
```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/testboost

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Observability
LANGSMITH_API_KEY=ls-...
LANGSMITH_PROJECT=testboost

# API Security
API_KEY=your-api-key-here

# Application
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### CHK005 T005 - Docker Compose

**Done when** `docker-compose.yaml` contient :
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: testboost
      POSTGRES_PASSWORD: testboost
      POSTGRES_DB: testboost
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U testboost"]
      interval: 5s
      timeout: 5s
      retries: 5

  testboost:
    build: .
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://testboost:testboost@postgres:5432/testboost
    ports:
      - "8000:8000"

volumes:
  postgres_data:
```

---

## Phase 2: Foundational Details

### CHK006 T006 - SQLAlchemy Base

**File**: `src/db/__init__.py`

**Must export**:
- `Base` - declarative base for models
- `SessionLocal` - session factory
- `get_db` - dependency for FastAPI
- `engine` - SQLAlchemy engine

**Example implementation**:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.lib.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### CHK007-011 T007-T011 - Database Models

**Each model must have**:
1. `__tablename__` matching data-model.md
2. All columns with correct types
3. Foreign keys with proper relationships
4. Enums for status fields
5. JSON columns for dynamic data
6. Timestamps with defaults

**Session model example**:
```python
from sqlalchemy import Column, String, Enum, DateTime, JSON
from sqlalchemy.orm import relationship
from src.db import Base
import enum

class SessionStatus(enum.Enum):
    pending = "pending"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    project_path = Column(String, nullable=False)
    workflow_type = Column(String, nullable=False)
    status = Column(Enum(SessionStatus), nullable=False, default=SessionStatus.pending)
    mode = Column(String, nullable=False, default="interactive")
    config = Column(JSON, default={})
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    steps = relationship("Step", back_populates="session")
    events = relationship("Event", back_populates="session")
    artifacts = relationship("Artifact", back_populates="session")
```

### CHK012 T012 - Alembic Migrations

**Setup**:
```bash
alembic init src/db/migrations
```

**Edit** `alembic.ini`:
```ini
script_location = src/db/migrations
```

**Edit** `src/db/migrations/env.py`:
```python
from src.db import Base
from src.db.models import *  # Import all models
target_metadata = Base.metadata
```

**Generate migration**:
```bash
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

### CHK013 T013 - Repository Pattern

**Base repository interface**:
```python
class BaseRepository:
    def __init__(self, db: Session, model: Type[T]):
        self.db = db
        self.model = model

    def create(self, **kwargs) -> T: ...
    def get(self, id: str) -> T | None: ...
    def list(self, skip: int = 0, limit: int = 100, **filters) -> list[T]: ...
    def update(self, id: str, **kwargs) -> T | None: ...
    def delete(self, id: str) -> bool: ...
```

### CHK014 T014 - Configuration

**Pydantic Settings class**:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    langsmith_api_key: str | None = None
    langsmith_project: str = "testboost"
    api_key: str
    log_level: str = "INFO"
    environment: str = "development"

    class Config:
        env_file = ".env"

_settings = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

### CHK015-016 T015-T016 - Logging

**Structlog configuration**:
```python
import structlog

def configure_logging(log_level: str, environment: str):
    processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        mask_sensitive_data,  # T016
    ]

    if environment == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(processors=processors)

def mask_sensitive_data(logger, method_name, event_dict):
    sensitive_keys = ["password", "token", "api_key", "secret", "key"]
    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in sensitive_keys):
            value = str(event_dict[key])
            if len(value) > 8:
                event_dict[key] = f"{value[:4]}...{value[-4:]}"
            else:
                event_dict[key] = "***"
    return event_dict
```

### CHK017 T017 - Event Service

**Interface**:
```python
class EventService:
    def __init__(self, db: Session):
        self.repo = EventRepository(db)

    def emit(self, session_id: str, event_type: str, data: dict, step_code: str | None = None):
        event = self.repo.create(
            session_id=session_id,
            step_code=step_code,
            event_type=event_type,
            event_data=data
        )
        return event

    def get_events(self, session_id: str, event_type: str | None = None) -> list[Event]:
        filters = {"session_id": session_id}
        if event_type:
            filters["event_type"] = event_type
        return self.repo.list(**filters)
```

### CHK018 T018 - Lock Service

**Interface**:
```python
class LockService:
    def __init__(self, db: Session):
        self.repo = ProjectLockRepository(db)

    def acquire_lock(self, project_path: str, session_id: str, ttl_seconds: int = 3600) -> bool:
        # Check if already locked by another session
        existing = self.repo.get_by_path(project_path)
        if existing and existing.session_id != session_id:
            if existing.expires_at > datetime.utcnow():
                return False
        # Create or update lock
        ...
        return True

    def release_lock(self, project_path: str, session_id: str) -> bool: ...
    def is_locked(self, project_path: str) -> bool: ...
    def cleanup_expired(self) -> int: ...
```

### CHK019-023 T019-T023 - API Foundation

**FastAPI app setup** (`src/api/main.py`):
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="TestBoost API",
    version="1.0.0",
    description="Automated Java project maintenance and testing"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(sessions_router, prefix="/api/v2")
app.include_router(testboost_router, prefix="/api/testboost")
```

### CHK024-026 T024-T026 - LangGraph Foundation

**LLM Factory**:
```python
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def get_llm(provider: str = "openai", model: str | None = None):
    settings = get_settings()
    if provider == "openai":
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=model or "gpt-4o",
            timeout=60
        )
    elif provider == "anthropic":
        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=model or "claude-3-5-sonnet-20241022",
            timeout=60
        )
```

**Workflow State**:
```python
from typing import TypedDict, Literal

class WorkflowState(TypedDict):
    session_id: str
    project_path: str
    mode: Literal["interactive", "autonomous", "analysis"]
    current_step: str
    error: str | None
    # Step-specific data added dynamically
```

---

## User Story Validation Scenarios

### US1 - Maven Maintenance E2E

**Test on TP1 (small)**:
```bash
boost maintenance test-projects/java-maven-junit-helloworld --mode autonomous
```

**Expected**:
- [ ] Détecte dépendances obsolètes (junit, etc.)
- [ ] Tests baseline passent
- [ ] Branche maintenance créée
- [ ] Updates appliqués
- [ ] Tests post-update passent
- [ ] Rapport généré

**Test on TP2 (medium)**:
```bash
boost maintenance test-projects/spring-petclinic-reactjs --mode autonomous
```

**Expected**:
- [ ] Détecte 10+ dépendances Spring
- [ ] Classifie par risque (patch/minor/major)
- [ ] Release notes récupérées
- [ ] Rollback si tests échouent

### US2 - Test Generation E2E

**Test on TP1**:
```bash
boost tests test-projects/java-maven-junit-helloworld --mode autonomous
```

**Expected**:
- [ ] Tests unitaires générés
- [ ] Compilation OK
- [ ] Score mutation ≥ 80%

**Test on TP2**:
- [ ] Tests pour Controllers avec MockMvc
- [ ] Tests pour Services avec mocks
- [ ] Tests d'intégration avec @SpringBootTest
- [ ] Score mutation ≥ 80%

### US3 - Docker Deployment E2E

**Test on TP2**:
```bash
boost deploy test-projects/spring-petclinic-reactjs --mode autonomous
```

**Expected**:
- [ ] Dockerfile multi-stage généré
- [ ] docker-compose.yaml avec DB
- [ ] Health check OK sur :8080
- [ ] Application fonctionnelle

**Test on TP3**:
- [ ] Docker Compose avec tous services
- [ ] Config Server démarre premier
- [ ] Gateway accessible
- [ ] Tous services healthy

---

## CI/CD Automation

### GitHub Actions Workflow

```yaml
name: Validate Implementation

on: [push, pull_request]

jobs:
  setup-test-projects:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Clone test projects
        run: |
          mkdir -p test-projects
          git clone --depth 1 https://github.com/LableOrg/java-maven-junit-helloworld test-projects/java-maven-junit-helloworld
          git clone --depth 1 https://github.com/spring-petclinic/spring-petclinic-reactjs test-projects/spring-petclinic-reactjs
          git clone --depth 1 https://github.com/spring-petclinic/spring-petclinic-microservices test-projects/spring-petclinic-microservices

  unit-tests:
    needs: setup-test-projects
    runs-on: ubuntu-latest
    steps:
      - name: Run pytest
        run: pytest tests/ -v --tb=short

  e2e-small:
    needs: unit-tests
    runs-on: ubuntu-latest
    steps:
      - name: Test on small project
        run: boost maintenance test-projects/java-maven-junit-helloworld --mode autonomous

  e2e-medium:
    needs: e2e-small
    runs-on: ubuntu-latest
    steps:
      - name: Test on medium project
        run: boost maintenance test-projects/spring-petclinic-reactjs --mode autonomous
```

---

## Notes

- Cocher les items une fois validés : `[x]`
- Ajouter des commentaires sur les problèmes rencontrés
- Les commandes de validation sont dans `tasks.md` (format compact)
- Ce fichier contient les détails complets et exemples de code
