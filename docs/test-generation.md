# Test Generation

Documentation for TestBoost test generation capabilities.

## Overview

TestBoost generates unit, integration, and snapshot tests for Java classes using LLM-powered analysis.

## Test Quality Scoring (CHK057)

### Scoring Formula

Tests are scored on a 0-120 point scale across six dimensions:

| Dimension | Max Points | Weight | Description |
|-----------|------------|--------|-------------|
| Coverage | 30 | 25% | Line and branch coverage |
| Assertions | 20 | 17% | Assertion quality and variety |
| Edge Cases | 20 | 17% | Boundary and null handling |
| Readability | 15 | 12% | Naming and structure |
| Isolation | 20 | 17% | Mock usage and independence |
| Mutation | 15 | 12% | Mutation survival rate |

### Detailed Scoring Breakdown

#### Coverage Score (0-30)

```
coverage_score = (line_coverage * 0.4 + branch_coverage * 0.6) * 30

- Line coverage: Percentage of lines executed
- Branch coverage: Percentage of branches taken
- Higher weight on branches (more valuable)
```

#### Assertion Score (0-20)

```
assertion_score = min(20, (
    assertion_count * 2 +
    unique_assertion_types * 3 +
    deep_equality_assertions * 2
))

Assertion types:
- assertEquals/assertNotEquals
- assertTrue/assertFalse
- assertNull/assertNotNull
- assertThrows
- assertThat (Hamcrest/AssertJ)
```

#### Edge Case Score (0-20)

```
edge_case_score = (
    null_handling_tests * 4 +
    boundary_tests * 4 +
    empty_collection_tests * 3 +
    exception_tests * 3 +
    concurrent_tests * 3
) capped at 20
```

#### Readability Score (0-15)

```
readability_score = (
    descriptive_names * 3 +      # test method names describe behavior
    arrange_act_assert * 3 +     # AAA pattern followed
    single_assertion_focus * 3 + # each test tests one thing
    comment_quality * 3 +        # useful comments
    reasonable_length * 3        # not too long
) capped at 15
```

#### Isolation Score (0-20)

```
isolation_score = (
    no_shared_state * 5 +        # tests don't share mutable state
    mocks_used_properly * 5 +    # dependencies are mocked
    no_external_deps * 5 +       # no file/network in unit tests
    test_independence * 5        # can run in any order
) capped at 20
```

#### Mutation Score (0-15)

```
mutation_score = mutation_kill_rate * 15

- Based on PIT mutation testing results
- Higher kill rate = better assertions
```

### Quality Grades

| Score | Grade | Description |
|-------|-------|-------------|
| 100-120 | A+ | Excellent, production-ready |
| 90-99 | A | Very good, minor improvements possible |
| 80-89 | B | Good, some gaps |
| 70-79 | C | Acceptable, needs improvement |
| 60-69 | D | Poor, significant gaps |
| < 60 | F | Failing, regeneration recommended |

## Cyclomatic Complexity Threshold (CHK061)

### Maximum Complexity for Auto-Generation

| Complexity | Auto-Generate | Action |
|------------|---------------|--------|
| 1-10 | Yes | Full test generation |
| 11-20 | Partial | Generate with warnings |
| 21-30 | Limited | Suggest refactoring first |
| 31+ | No | Manual testing required |

### Complexity Calculation

```java
// Example: Cyclomatic complexity = 4
public String classify(int score) {
    if (score >= 90) {           // +1
        return "A";
    } else if (score >= 80) {    // +1
        return "B";
    } else if (score >= 70) {    // +1
        return "C";
    } else {
        return "F";
    }
}  // Base = 1, Decisions = 3, Total = 4
```

### Handling Complex Classes

For classes with complexity > 20:

1. **Decomposition Suggestion**
   ```
   Class `OrderProcessor` has complexity 35.
   Suggested decomposition:
   - Extract `validateOrder()` to OrderValidator
   - Extract `calculateTotal()` to PriceCalculator
   - Extract `applyDiscounts()` to DiscountEngine
   ```

2. **Partial Test Generation**
   - Generate tests for simple methods only
   - Flag complex methods for manual testing
   - Provide test scaffolding for complex methods

3. **Complexity Report**
   ```json
   {
     "class": "OrderProcessor",
     "overall_complexity": 35,
     "methods": [
       {"name": "processOrder", "complexity": 18},
       {"name": "validatePayment", "complexity": 12},
       {"name": "calculateShipping", "complexity": 5}
     ],
     "recommendation": "refactor_before_testing"
   }
   ```

## External Mock Generation (CHK062)

### Mockito Patterns

TestBoost generates tests using Mockito for external dependencies:

#### Basic Mock Setup

```java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock
    private PaymentGateway paymentGateway;

    @Mock
    private InventoryService inventoryService;

    @InjectMocks
    private OrderService orderService;

    @Test
    void shouldProcessOrderSuccessfully() {
        // Arrange
        Order order = new Order("item-1", 2);
        when(inventoryService.checkStock("item-1")).thenReturn(true);
        when(paymentGateway.charge(anyDouble())).thenReturn(PaymentResult.SUCCESS);

        // Act
        OrderResult result = orderService.process(order);

        // Assert
        assertThat(result.getStatus()).isEqualTo(OrderStatus.COMPLETED);
        verify(paymentGateway).charge(order.getTotal());
    }
}
```

#### External Service Mock Strategy

| Service Type | Mock Strategy | Example |
|--------------|---------------|---------|
| HTTP Client | Mock at client level | `when(httpClient.get(url)).thenReturn(response)` |
| Database | Mock repository | `when(userRepo.findById(id)).thenReturn(user)` |
| Message Queue | Mock producer/consumer | `doNothing().when(producer).send(message)` |
| Cache | Mock cache client | `when(cache.get(key)).thenReturn(value)` |
| File System | Use temp directories | `@TempDir Path tempDir` |

#### Generated Mock Verification

```java
@Test
void shouldRetryOnTransientFailure() {
    // Arrange
    when(externalService.call())
        .thenThrow(new TransientException())
        .thenReturn("success");

    // Act
    String result = serviceUnderTest.callWithRetry();

    // Assert
    assertThat(result).isEqualTo("success");
    verify(externalService, times(2)).call();
}
```

### Mock Generation Rules

1. **Identify Dependencies**: Parse constructor and field injections
2. **Classify Dependency Type**: Service, Repository, Client, etc.
3. **Generate Appropriate Mocks**: Based on method signatures
4. **Add Verification**: Verify critical interactions

## ApprovalTests Snapshot Pattern (CHK060)

### Snapshot File Format

Snapshot files are stored alongside test files with `.approved.txt` extension:

```
src/test/java/com/example/OrderServiceTest.java
src/test/java/com/example/OrderServiceTest.shouldGenerateInvoice.approved.txt
```

### Snapshot Content Format

```
=== Test: shouldGenerateInvoice ===
Timestamp: 2024-01-01T00:00:00Z
Input:
  orderId: "order-123"
  items: ["item-1", "item-2"]
  total: 99.99

Output:
  Invoice #INV-2024-001
  Date: 2024-01-01
  Items:
    - item-1: $49.99
    - item-2: $50.00
  Total: $99.99
  Status: GENERATED
```

### Approval Workflow

```
┌──────────────┐
│ Run Test     │
└──────┬───────┘
       │
       ▼
┌──────────────┐     ┌──────────────┐
│ .received.txt│────>│ Compare      │
└──────────────┘     └──────┬───────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
            ▼                               ▼
    ┌──────────────┐               ┌──────────────┐
    │ Match        │               │ Difference   │
    │ (Pass)       │               │ (Review)     │
    └──────────────┘               └──────┬───────┘
                                          │
                           ┌──────────────┴──────────────┐
                           │                             │
                           ▼                             ▼
                   ┌──────────────┐             ┌──────────────┐
                   │ Approve      │             │ Reject       │
                   │ (copy to     │             │ (fix code)   │
                   │  .approved)  │             │              │
                   └──────────────┘             └──────────────┘
```

### Generated Snapshot Test

```java
@Test
void shouldGenerateInvoice() {
    // Arrange
    Order order = createTestOrder();

    // Act
    Invoice invoice = invoiceService.generate(order);

    // Assert using ApprovalTests
    Approvals.verify(invoice.toString());
}
```

### Snapshot Configuration

```java
// In test base class or configuration
@BeforeAll
static void configureApprovals() {
    // Store snapshots in resources directory
    Approvals.registerDefaultApprover(
        new FileApprover(Path.of("src/test/resources/snapshots"))
    );

    // Use JSON format for complex objects
    Approvals.registerSerializer(
        Order.class,
        order -> new ObjectMapper().writeValueAsString(order)
    );
}
```

### When to Use Snapshots

| Use Case | Snapshot Appropriate | Alternative |
|----------|---------------------|-------------|
| Complex object output | Yes | N/A |
| Generated reports | Yes | N/A |
| API response format | Yes | N/A |
| Simple value check | No | assertEquals |
| Boolean condition | No | assertTrue |
| Exception check | No | assertThrows |

## Test Generation Configuration

### Agent Configuration

```yaml
# In config/agents/test_gen_agent.yaml
test_generation:
  coverage_target: 0.80
  max_complexity: 20
  mock_framework: mockito
  assertion_library: assertj
  snapshot_enabled: true
  snapshot_format: text  # or json
```

### Per-Class Overrides

```java
// Annotation-based configuration
@TestGenConfig(
    coverageTarget = 0.90,
    maxComplexity = 25,
    skipMethods = {"toString", "hashCode"}
)
public class OrderService {
    // ...
}
```

## Artifact Storage Pattern

### Write-Before-Register Pattern

**Critical requirement**: All workflow artifacts (test failures, metrics, compilation errors, agent reasoning) must be written to disk BEFORE creating database records.

#### Correct Pattern

```python
# 1. Write file to disk FIRST
file_path = f"artifacts/{session_id}/metrics/file.json"
path = Path(file_path)
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(content, indent=2), encoding="utf-8")

# 2. Calculate actual file size
size_bytes = path.stat().st_size

# 3. Create database record AFTER file exists
await artifact_repo.create(
    session_id=session_id,
    name="artifact_name",
    artifact_type="artifact_type",
    file_path=file_path,
    size_bytes=size_bytes,
)
```

#### Anti-Pattern (Bug)

```python
# ❌ WRONG: Creating DB record without writing file
await artifact_repo.create(
    file_path=f"artifacts/{session_id}/metrics/file.json",
    size_bytes=len(json.dumps(content)),  # calculated but not written!
)
# Result: 404 errors when retrieving artifact content
```

### Why This Matters

The `ArtifactRepository.create()` method only creates database records—it does NOT write files. The workflow code is responsible for:

1. Creating the directory structure (`mkdir -p`)
2. Writing the file content to disk
3. Getting the actual file size (not estimated)
4. Creating the database record with the correct path and size

### Locations Using This Pattern

All artifact storage in `test_generation_agent.py`:
- `_store_generation_metrics()` - Test generation summary
- `_store_llm_metrics()` - LLM usage statistics
- `_store_agent_reasoning()` - Agent decision logs
- `_store_tool_calls()` - MCP tool invocation history
- `_store_test_file_artifacts()` - Generated test files
- Compilation error storage - Compiler output
- Test failure storage - Test execution results

### Verification

To verify artifacts are properly stored:

```bash
# Check DB records exist
curl http://localhost:8000/api/v2/sessions/{id}/artifacts

# Check files exist on disk
ls -la artifacts/{session_id}/

# Test retrieval (should NOT return 404)
curl http://localhost:8000/api/v2/sessions/{id}/artifacts/{artifact_id}/content
```
