# Snapshot Test Strategy Prompt Template

## System Prompt

You are an expert Java test engineer specializing in snapshot testing for API responses, serialization formats, and deterministic outputs. Your task is to generate effective snapshot tests that catch unintended changes while allowing intentional updates.

## Context Variables

- `{class_name}`: Name of the class to test
- `{class_type}`: Type of class (controller, dto, serializer)
- `{package}`: Package name
- `{endpoints}`: API endpoints (for controllers)
- `{snapshot_format}`: Format for snapshots (json, xml, text)
- `{serialization_fields}`: Fields to include in serialization

## Test Generation Prompt

Generate snapshot tests for the following Java component:

### Component Information
- **Name**: {class_name}
- **Type**: {class_type}
- **Package**: {package}
- **Snapshot Format**: {snapshot_format}

### Generation Requirements

1. **Snapshot Storage**:
   - Store snapshots in `src/test/resources/snapshots/`
   - Use descriptive naming: `{classname}_{scenario}.{format}`
   - Support automatic snapshot creation on first run

2. **Comparison Strategy**:
   - Compare entire response/serialization
   - Use flexible matchers for dynamic fields (timestamps, IDs)
   - Provide clear diff output on failure

3. **Maintenance**:
   - Easy snapshot update mechanism
   - Clear documentation of snapshot purpose
   - Version control friendly format

## Snapshot Test Patterns

### API Response Snapshot Test
```java
@WebMvcTest({class_name}.class)
@DisplayName("{class_name} Snapshot Tests")
class {class_name}SnapshotTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private {service} service;

    private final ObjectMapper objectMapper = new ObjectMapper()
            .enable(SerializationFeature.INDENT_OUTPUT);

    private static final String SNAPSHOTS_DIR = "src/test/resources/snapshots";

    @Test
    @DisplayName("Snapshot: GET /api/resources response format")
    void snapshotGetResourcesResponse() throws Exception {
        // Arrange
        when(service.findAll()).thenReturn(createTestResources());

        // Act
        MvcResult result = mockMvc.perform(get("/api/resources")
                .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andReturn();

        // Assert
        String response = result.getResponse().getContentAsString();
        String formatted = formatJson(response);

        assertMatchesSnapshot(formatted, "{class_name_lower}_list.json");
    }

    @Test
    @DisplayName("Snapshot: GET /api/resources/{id} response format")
    void snapshotGetResourceByIdResponse() throws Exception {
        // Arrange
        when(service.findById(1L)).thenReturn(Optional.of(createTestResource()));

        // Act
        MvcResult result = mockMvc.perform(get("/api/resources/1")
                .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andReturn();

        // Assert
        String response = result.getResponse().getContentAsString();
        String formatted = formatJson(response);

        assertMatchesSnapshot(formatted, "{class_name_lower}_detail.json");
    }

    @Test
    @DisplayName("Snapshot: Error response format")
    void snapshotErrorResponse() throws Exception {
        // Arrange
        when(service.findById(999L)).thenReturn(Optional.empty());

        // Act
        MvcResult result = mockMvc.perform(get("/api/resources/999")
                .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isNotFound())
                .andReturn();

        // Assert
        String response = result.getResponse().getContentAsString();
        String formatted = formatJson(response);

        assertMatchesSnapshot(formatted, "{class_name_lower}_not_found.json");
    }

    private void assertMatchesSnapshot(String actual, String snapshotName) throws Exception {
        Path snapshotPath = Paths.get(SNAPSHOTS_DIR, snapshotName);

        if (!Files.exists(snapshotPath)) {
            // Create snapshot on first run
            Files.createDirectories(snapshotPath.getParent());
            Files.writeString(snapshotPath, actual);
            System.out.println("Created snapshot: " + snapshotName);
            return;
        }

        String expected = Files.readString(snapshotPath);

        // Use JSONAssert for flexible JSON comparison
        JSONAssert.assertEquals(
                expected,
                actual,
                JSONCompareMode.STRICT
        );
    }

    private String formatJson(String json) throws Exception {
        Object parsed = objectMapper.readValue(json, Object.class);
        return objectMapper.writeValueAsString(parsed);
    }
}
```

### DTO Serialization Snapshot Test
```java
@DisplayName("{class_name} Serialization Snapshot Tests")
class {class_name}SnapshotTest {

    private final ObjectMapper objectMapper = new ObjectMapper()
            .enable(SerializationFeature.INDENT_OUTPUT)
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

    private static final String SNAPSHOTS_DIR = "src/test/resources/snapshots";

    @Test
    @DisplayName("Snapshot: Full serialization format")
    void snapshotFullSerialization() throws Exception {
        // Arrange
        {class_name} dto = createFullyPopulatedDto();

        // Act
        String json = objectMapper.writeValueAsString(dto);

        // Assert
        assertMatchesSnapshot(json, "{class_name_lower}_full.json");
    }

    @Test
    @DisplayName("Snapshot: Minimal serialization (nulls excluded)")
    void snapshotMinimalSerialization() throws Exception {
        // Arrange
        {class_name} dto = createMinimalDto();

        // Act
        String json = objectMapper.writeValueAsString(dto);

        // Assert
        assertMatchesSnapshot(json, "{class_name_lower}_minimal.json");
    }

    @Test
    @DisplayName("Snapshot: Serialization with nested objects")
    void snapshotWithNestedObjects() throws Exception {
        // Arrange
        {class_name} dto = createDtoWithNestedObjects();

        // Act
        String json = objectMapper.writeValueAsString(dto);

        // Assert
        assertMatchesSnapshot(json, "{class_name_lower}_nested.json");
    }

    @Test
    @DisplayName("Deserialization roundtrip preserves data")
    void deserializationRoundtrip() throws Exception {
        // Arrange
        {class_name} original = createFullyPopulatedDto();

        // Act
        String json = objectMapper.writeValueAsString(original);
        {class_name} deserialized = objectMapper.readValue(json, {class_name}.class);

        // Assert - using recursive comparison to check all fields
        assertThat(deserialized)
                .usingRecursiveComparison()
                .isEqualTo(original);
    }

    private void assertMatchesSnapshot(String actual, String snapshotName) throws Exception {
        Path snapshotPath = Paths.get(SNAPSHOTS_DIR, snapshotName);

        if (!Files.exists(snapshotPath)) {
            Files.createDirectories(snapshotPath.getParent());
            Files.writeString(snapshotPath, actual);
            System.out.println("Created snapshot: " + snapshotName);
            return;
        }

        String expected = Files.readString(snapshotPath);
        assertThat(actual).isEqualToIgnoringWhitespace(expected);
    }
}
```

### Dynamic Field Handling
```java
@Test
@DisplayName("Snapshot: Response with dynamic fields")
void snapshotWithDynamicFields() throws Exception {
    // Act
    MvcResult result = mockMvc.perform(post("/api/resources")
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"name\": \"test\"}"))
            .andExpect(status().isCreated())
            .andReturn();

    // Mask dynamic fields before snapshot comparison
    String response = result.getResponse().getContentAsString();
    String masked = maskDynamicFields(response);

    assertMatchesSnapshot(masked, "create_response.json");
}

private String maskDynamicFields(String json) throws Exception {
    JsonNode node = objectMapper.readTree(json);

    // Mask timestamp fields
    if (node.has("createdAt")) {
        ((ObjectNode) node).put("createdAt", "{{TIMESTAMP}}");
    }
    if (node.has("updatedAt")) {
        ((ObjectNode) node).put("updatedAt", "{{TIMESTAMP}}");
    }

    // Mask generated IDs
    if (node.has("id")) {
        ((ObjectNode) node).put("id", "{{ID}}");
    }

    return objectMapper.writeValueAsString(node);
}
```

## Snapshot File Examples

### JSON Snapshot Example
```json
{
  "id": 1,
  "name": "Test Resource",
  "status": "ACTIVE",
  "metadata": {
    "version": 1,
    "tags": ["test", "sample"]
  },
  "links": {
    "self": "/api/resources/1",
    "collection": "/api/resources"
  }
}
```

### XML Snapshot Example
```xml
<?xml version="1.0" encoding="UTF-8"?>
<resource>
  <id>1</id>
  <name>Test Resource</name>
  <status>ACTIVE</status>
</resource>
```

## Expected Output Format

Generate complete snapshot test class with:

```java
package {package};

// Imports...

@DisplayName("{class_name} Snapshot Tests")
class {class_name}SnapshotTest {

    // ObjectMapper configuration
    // Snapshot directory constant

    // Test methods for each snapshot scenario

    // Helper methods for snapshot comparison and formatting
}
```

## Quality Checklist

Before finalizing tests, verify:

1. [ ] Snapshots capture complete structure
2. [ ] Dynamic fields are properly handled
3. [ ] Snapshot files are readable and well-formatted
4. [ ] First-run creates snapshots automatically
5. [ ] Failures provide clear diffs
6. [ ] Snapshot updates are intentional
7. [ ] Edge cases are covered (nulls, empty, nested)
