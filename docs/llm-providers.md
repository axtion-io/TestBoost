# LLM Providers

TestBoost uses LLMs for project analysis and test generation. It supports three providers, all interchangeable with zero code changes.

## Supported Providers

| Provider | Recommended Model | Cost (1M tokens) | Typical Latency |
|----------|-------------------|-------------------|-----------------|
| **Google Gemini** | `gemini-2.5-flash` | $0.075 input / $0.30 output | 1-3s |
| **Anthropic Claude** | `claude-sonnet-4-20250514` | $3.00 input / $15.00 output | 2-5s |
| **OpenAI GPT-4o** | `gpt-4o` | $2.50 input / $10.00 output | 2-4s |

## Configuration

### Environment Variables

```bash
# Set the API key for your chosen provider
export GOOGLE_API_KEY="AIza..."       # Google Gemini
export ANTHROPIC_API_KEY="sk-ant-..." # Anthropic Claude
export OPENAI_API_KEY="sk-..."        # OpenAI

# Choose the provider and model (default: anthropic + claude-sonnet-4-6)
export LLM_PROVIDER="google-genai" && export MODEL="gemini-2.5-flash"
export LLM_PROVIDER="anthropic"    && export MODEL="claude-sonnet-4-6"
export LLM_PROVIDER="openai"       && export MODEL="gpt-4o"
```

You can also set these in a `.env` file at the TestBoost root.

### Switching Providers

Change the `MODEL` variable and make sure the corresponding API key is set. No code changes needed.

## Provider Comparison

### Google Gemini

**Best for:** Development, CI/CD, budget-conscious usage

- Free tier with 1500 requests/day
- Low latency
- Good value for money
- Occasional timeouts (504)

### Anthropic Claude

**Best for:** Highest quality test generation

- Excellent code generation quality
- Best reasoning on complex architectures
- Very reliable
- Higher cost

### OpenAI GPT-4o

**Best for:** General-purpose usage

- Versatile
- Good documentation ecosystem
- Moderate cost

## Cost Estimates

### Per Workflow Run

| Workflow Step | Tokens (approx.) | Gemini | Claude | GPT-4o |
|---------------|-------------------|--------|--------|--------|
| Analyze | ~5K input + 2K output | $0.001 | $0.045 | $0.033 |
| Generate (per file) | ~20K input + 10K output | $0.005 | $0.21 | $0.15 |

### Monthly Estimate (10 runs/day)

| Provider | Estimated Cost |
|----------|---------------|
| Gemini | ~$3 - $10 |
| Claude | ~$50 - $150 |
| GPT-4o | ~$40 - $100 |

## Observability

To trace LLM calls with LangSmith:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="lsv2_..."
export LANGSMITH_PROJECT="testboost"
```

## Error Handling

### Rate Limit (429)

```
LLM rate limit exceeded. Retry after {duration} seconds.
```

Wait for the indicated delay, reduce request frequency, or switch to a provider with a higher quota.

### Timeout

```
LLM request timeout after 120s
```

Check your network connection. Increase `LLM_TIMEOUT` in your `.env` if needed. Try again later if the provider is experiencing issues.

### Invalid API Key

```
API key not configured for provider 'anthropic'
```

Verify the environment variable is set and the key is valid. Regenerate the key if expired.

## Recommendations

| Use Case | Recommended Provider |
|----------|---------------------|
| Local development | Gemini (free tier) |
| CI/CD | Gemini (minimal cost) |
| Best quality | Claude |
| Budget-limited | Gemini |
| Large projects | Claude or GPT-4o |
