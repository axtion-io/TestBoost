# Integration Test Strategy Prompt Template

## System Prompt

You are an expert Java test engineer specializing in integration testing with Spring Boot Test, Testcontainers, and WireMock. Your task is to generate effective integration tests that verify component interactions and data flows.

## Context Variables

- `{class_name}`: Name of the class to test
- `{class_type}`: Type of class (service, repository, controller)
- `{package}`: Package name
- `{endpoints}`: API endpoints (for controllers)
- `{database_entities}`: Related database entities
- `{external_services}`: External service dependencies
- `{test_containers}`: Whether to use Testcontainers

## Test Generation Prompt

Generate integration tests for the following Java component:

### Component Information
- **Name**: {class_name}
- **Type**: {class_type}
- **Package**: {package}

### Integration Points
- **Database Entities**: {database_entities}
- **External Services**: {external_services}
- **API Endpoints**: {endpoints}

### Generation Requirements

1. **Test Annotations**:
   - Use appropriate Spring test slice (@WebMvcTest, @DataJpaTest, @SpringBootTest)
   - Configure Testcontainers if database tests
   - Use WireMock for external service mocking

2. **Database Testing**:
   - Use Testcontainers for realistic database testing
   - Clean database state between tests
   - Test data persistence and retrieval

3. **API Testing**:
   - Test complete request/response cycles
   - Verify HTTP status codes and response bodies
   - Test error handling

4. **External Service Testing**:
   - Mock external services with WireMock
   - Test success and failure scenarios
   - Verify retry and fallback behavior

## Integration Test Patterns

### Repository Integration Test (with Testcontainers)
```java
@Testcontainers
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@DisplayName("{class_name} Integration Tests")
class {class_name}IntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15")
            .withDatabaseName("testdb")
            .withUsername("test")
            .withPassword("test");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired
    private TestEntityManager entityManager;

    @Autowired
    private {class_name} repository;

    @Test
    @DisplayName("Should save and retrieve entity with all fields")
    void shouldSaveAndRetrieveEntity() {
        // Arrange
        var entity = createTestEntity();

        // Act
        entityManager.persistAndFlush(entity);
        entityManager.clear();

        var result = repository.findById(entity.getId());

        // Assert
        assertThat(result).isPresent();
        assertThat(result.get().getName()).isEqualTo(entity.getName());
    }

    @Test
    @DisplayName("Should query by custom criteria")
    void shouldQueryByCustomCriteria() {
        // Arrange
        entityManager.persist(createTestEntity("active", true));
        entityManager.persist(createTestEntity("inactive", false));
        entityManager.flush();

        // Act
        var results = repository.findByActiveTrue();

        // Assert
        assertThat(results).hasSize(1);
        assertThat(results.get(0).getName()).isEqualTo("active");
    }
}
```

### Service Integration Test
```java
@SpringBootTest
@Transactional
@DisplayName("{class_name} Integration Tests")
class {class_name}IntegrationTest {

    @Autowired
    private {class_name} service;

    @Autowired
    private {repository_type} repository;

    @Test
    @DisplayName("Should process complete business flow")
    void shouldProcessCompleteBusinessFlow() {
        // Arrange
        var input = createTestInput();

        // Act
        var result = service.processBusinessFlow(input);

        // Assert
        assertThat(result).isNotNull();
        assertThat(result.getStatus()).isEqualTo("COMPLETED");

        // Verify persistence
        var persisted = repository.findById(result.getId());
        assertThat(persisted).isPresent();
    }

    @Test
    @DisplayName("Should handle transaction rollback on failure")
    void shouldRollbackOnFailure() {
        // Arrange
        var input = createInvalidInput();

        // Act & Assert
        assertThatThrownBy(() -> service.processBusinessFlow(input))
                .isInstanceOf(BusinessException.class);

        // Verify no data persisted
        assertThat(repository.count()).isZero();
    }
}
```

### Controller Integration Test
```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureMockMvc
@DisplayName("{class_name} Integration Tests")
class {class_name}IntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private {repository_type} repository;

    @Test
    @DisplayName("Should create resource and return 201")
    void shouldCreateResource() throws Exception {
        // Arrange
        var request = createTestRequest();

        // Act
        var result = mockMvc.perform(post("/api/resources")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
                .andReturn();

        // Assert response
        var response = objectMapper.readValue(
                result.getResponse().getContentAsString(),
                ResourceResponse.class
        );
        assertThat(response.getId()).isNotNull();

        // Verify persistence
        var persisted = repository.findById(response.getId());
        assertThat(persisted).isPresent();
    }

    @Test
    @DisplayName("Should return 400 for invalid request")
    void shouldReturn400ForInvalidRequest() throws Exception {
        // Arrange
        var invalidRequest = createInvalidRequest();

        // Act & Assert
        mockMvc.perform(post("/api/resources")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(invalidRequest)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.errors").isArray());
    }
}
```

### External Service Integration Test (with WireMock)
```java
@SpringBootTest
@WireMockTest(httpPort = 8089)
@DisplayName("{class_name} Integration Tests")
class {class_name}IntegrationTest {

    @Autowired
    private {class_name} service;

    @Test
    @DisplayName("Should call external API and process response")
    void shouldCallExternalApiSuccessfully() {
        // Arrange
        stubFor(get(urlEqualTo("/api/external/resource/1"))
                .willReturn(aResponse()
                        .withStatus(200)
                        .withHeader("Content-Type", "application/json")
                        .withBody("{\"id\": 1, \"status\": \"active\"}")));

        // Act
        var result = service.getExternalResource(1L);

        // Assert
        assertThat(result).isNotNull();
        assertThat(result.getStatus()).isEqualTo("active");

        // Verify API call
        verify(getRequestedFor(urlEqualTo("/api/external/resource/1")));
    }

    @Test
    @DisplayName("Should handle external API failure gracefully")
    void shouldHandleExternalApiFailure() {
        // Arrange
        stubFor(get(urlEqualTo("/api/external/resource/1"))
                .willReturn(aResponse().withStatus(500)));

        // Act & Assert
        assertThatThrownBy(() -> service.getExternalResource(1L))
                .isInstanceOf(ExternalServiceException.class)
                .hasMessageContaining("External service unavailable");
    }

    @Test
    @DisplayName("Should retry on transient failure")
    void shouldRetryOnTransientFailure() {
        // Arrange - first call fails, second succeeds
        stubFor(get(urlEqualTo("/api/external/resource/1"))
                .inScenario("Retry")
                .whenScenarioStateIs(Scenario.STARTED)
                .willReturn(aResponse().withStatus(503))
                .willSetStateTo("Recovered"));

        stubFor(get(urlEqualTo("/api/external/resource/1"))
                .inScenario("Retry")
                .whenScenarioStateIs("Recovered")
                .willReturn(aResponse()
                        .withStatus(200)
                        .withBody("{\"id\": 1}")));

        // Act
        var result = service.getExternalResource(1L);

        // Assert
        assertThat(result).isNotNull();
        verify(2, getRequestedFor(urlEqualTo("/api/external/resource/1")));
    }
}
```

## Expected Output Format

Generate complete integration test class with:

```java
package {package};

// Imports...

// Annotations for test type
@DisplayName("{class_name} Integration Tests")
class {class_name}IntegrationTest {

    // Container definitions (if using Testcontainers)
    // Dynamic property sources (if needed)
    // Autowired dependencies

    // Test methods with realistic integration scenarios
}
```

## Quality Checklist

Before finalizing tests, verify:

1. [ ] Tests verify actual integration behavior
2. [ ] Database state is properly managed
3. [ ] External services are properly mocked
4. [ ] Transaction behavior is tested
5. [ ] Error scenarios are covered
6. [ ] Tests are isolated and repeatable
7. [ ] Performance considerations are addressed
