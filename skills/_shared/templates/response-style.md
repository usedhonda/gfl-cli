# Response Style Template

## Response Language

- User language:
- Final answer language:
- Language detection note:

Language resolution order:

1. Explicit language request in the current user message
2. Dominant language in the current user message
3. Last confirmed user language in the current session
4. Fallback: English

## Do Not Translate Tokens

- `gfl`
- `gfl search`
- `gfl calendar`
- `gfl version`
- `--origin --destination --date --return-date --segment --currency --view`
- `status`
- `request_id`
- `query`
- `results`
- `meta`
- `error`
- `INVALID_INPUT`
- `UPSTREAM_FORMAT_CHANGED`
- `UPSTREAM_UNAVAILABLE`
- `RATE_LIMITED`
- `TIMEOUT`
- `INTERNAL_ERROR`

## Output Checklist

- prose localized to user language
- technical tokens kept canonical
- recommendations are actionable
