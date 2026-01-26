# TestBoost Test Scenarios

Detailed test scenarios for comprehensive feature validation.

## Scenario 1: New User Onboarding

**Objective:** Verify a new user can successfully set up and run their first maintenance check.

### Pre-conditions
- Clean installation of TestBoost
- PostgreSQL running
- Valid Java project available

### Steps

1. **Install TestBoost**
   ```bash
   pip install -e ".[dev]"
   ```
   Expected: Installation completes without errors

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with database credentials
   ```
   Expected: Environment file created

3. **Verify Installation**
   ```bash
   python -m src.cli.main --help
   ```
   Expected: Help displayed with available commands

4. **Run First Analysis**
   ```bash
   python -m src.cli.main maintenance list ./my-project
   ```
   Expected: Dependency analysis report displayed

5. **Check API Access**
   ```bash
   curl http://localhost:8000/health
   ```
   Expected: Health status returned

### Success Criteria
- All commands execute successfully
- Clear output at each step
- No cryptic error messages

---

## Scenario 2: Maven Dependency Update Cycle

**Objective:** Complete end-to-end dependency update workflow.

### Pre-conditions
- Project with outdated dependencies
- Database running
- Backup of original pom.xml files

### Steps

1. **Analyze Current State**
   ```bash
   python -m src.cli.main maintenance list ./project-with-updates
   ```
   Expected: List shows dependencies with available updates

2. **Preview Updates (Dry Run)**
   ```bash
   python -m src.cli.main maintenance run ./project-with-updates --dry-run
   ```
   Expected: Shows what would be changed without modifying files

3. **Apply Updates**
   ```bash
   python -m src.cli.main maintenance run ./project-with-updates
   ```
   Expected: pom.xml files updated, backup created

4. **Verify Changes**
   ```bash
   git diff ./project-with-updates/pom.xml
   ```
   Expected: Version numbers updated appropriately

5. **Validate Build**
   ```bash
   cd ./project-with-updates && mvn compile
   ```
   Expected: Project compiles successfully with new versions

### Rollback Procedure
If build fails:
```bash
# Restore from backup
cp ./project-with-updates/pom.xml.backup ./project-with-updates/pom.xml
```

---

## Scenario 3: Test Generation with LLM

**Objective:** Generate meaningful unit tests using LLM integration.

### Pre-conditions
- LLM API credentials configured
- Java project with untested classes
- Sufficient API quota

### Steps

1. **Analyze Test Coverage**
   ```bash
   python -m src.cli.main tests analyze ./my-project
   ```
   Expected: Coverage report showing untested classes

2. **Generate Tests for Single Class**
   ```bash
   python -m src.cli.main tests generate ./my-project \
     --class com.example.UserService \
     --verbose
   ```
   Expected: JUnit test file created with meaningful test cases

3. **Review Generated Code**
   - Open generated test file
   - Verify imports are correct
   - Check test method names are descriptive
   - Confirm assertions are meaningful

4. **Run Generated Tests**
   ```bash
   cd ./my-project && mvn test -Dtest=UserServiceTest
   ```
   Expected: Tests compile and run (may fail initially - expected)

5. **Batch Generation**
   ```bash
   python -m src.cli.main tests generate ./my-project
   ```
   Expected: Tests generated for all untested classes

### Quality Checks
- [ ] Generated tests follow project naming conventions
- [ ] Mock dependencies injected correctly
- [ ] Edge cases covered (null, empty, boundary values)
- [ ] No hardcoded test data that could cause failures

---

## Scenario 4: API Session Lifecycle

**Objective:** Verify complete session management through API.

### Steps

1. **Create Session**
   ```bash
   SESSION=$(curl -s -X POST http://localhost:8000/api/v2/sessions \
     -H "Content-Type: application/json" \
     -d '{"project_path": "/path/to/project", "workflow_type": "maintenance"}' \
     | jq -r '.id')
   echo "Session ID: $SESSION"
   ```

2. **Check Session Status**
   ```bash
   curl -s http://localhost:8000/api/v2/sessions/$SESSION | jq .
   ```
   Expected: Status shows "pending" or "running"

3. **List Steps**
   ```bash
   curl -s http://localhost:8000/api/v2/sessions/$SESSION/steps | jq .
   ```
   Expected: Array of workflow steps

4. **Wait for Completion**
   ```bash
   while true; do
     STATUS=$(curl -s http://localhost:8000/api/v2/sessions/$SESSION | jq -r '.status')
     echo "Status: $STATUS"
     [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]] && break
     sleep 5
   done
   ```

5. **Retrieve Artifacts**
   ```bash
   curl -s http://localhost:8000/api/v2/sessions/$SESSION/artifacts | jq .
   ```
   Expected: List of generated artifacts

6. **Cleanup**
   ```bash
   curl -X DELETE http://localhost:8000/api/v2/sessions/$SESSION
   ```

---

## Scenario 5: Error Recovery

**Objective:** Verify system handles errors gracefully.

### Test Cases

| Test | Action | Expected Behavior |
|------|--------|-------------------|
| Invalid project path | Run command with `/nonexistent` | Clear error message, exit code 1 |
| Database disconnection | Kill PostgreSQL during operation | Graceful error, no data corruption |
| LLM timeout | Set very low timeout | Falls back to template mode |
| Concurrent modification | Edit pom.xml during update | Detects conflict, aborts safely |
| Disk full | Fill temp directory | Error message, cleanup attempted |

---

## Scenario 6: Performance Baseline

**Objective:** Establish performance expectations.

### Measurements

| Operation | Target | Method |
|-----------|--------|--------|
| CLI startup | < 2 seconds | `time python -m src.cli.main --help` |
| Health endpoint | < 100ms | `curl -w "%{time_total}" http://localhost:8000/health` |
| Small project analysis | < 30 seconds | `time python -m src.cli.main maintenance list ./small-project` |
| Large project (50+ POMs) | < 5 minutes | `time python -m src.cli.main maintenance list ./spring-petclinic` |

### Environment
- GitHub Actions runner: 2 vCPU, 7GB RAM
- Local development: Minimum 8GB RAM recommended
