# Search Intake Template

## Request Context

- User language:
- Final answer language:
- Goal:

## Query Inputs

- trip mode (`one-way|round-trip|multi-city`):
- origin:
- destination:
- date:
- return-date:
- segments (`FROM:TO:YYYY-MM-DD`, repeatable):
- lang:
- currency:

## Optional Filters

- seat:
- max-stops:
- airline list:
- sort mode:
- max-price:
- depart-after / depart-before:
- arrive-after / arrive-before:
- max-duration-min:

## Validation Checklist

- required fields by trip mode are complete
- date format is `YYYY-MM-DD`
- segment format is `FROM:TO:YYYY-MM-DD` when multi-city
- currency and language are explicit when required
