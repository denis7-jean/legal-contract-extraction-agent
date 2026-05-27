# n8n — Legal Contract Extraction Workflow

## Importing the workflow

1. Open your n8n instance (default: `http://localhost:5678`)
2. Go to **Workflows → Import from file**
3. Select `contract_extraction_workflow.json`
4. The workflow is imported in **inactive** state — do not activate until env vars are set

## Required environment variables

Set these in n8n under **Settings → Variables** (or in your `.env` for Docker deployments):

| Variable | Description | Example |
|---|---|---|
| `LEGAL_AGENT_API_URL` | Base URL of the FastAPI service | `http://localhost:8000` |
| `SLACK_WEBHOOK_URL` | Slack app incoming webhook URL for HIGH risk alerts | `https://hooks.slack.com/services/...` |
| `DATABASE_API_URL` | Persistence layer base URL for CLEAN/MEDIUM contract storage | `http://localhost:9000` |

The workflow uses `$env.VARIABLE_NAME` syntax — n8n resolves these at execution time.

## Activating the workflow

After setting all three environment variables:

1. Open the imported workflow
2. Toggle the **Active** switch in the top-right corner
3. The webhook URL becomes live at: `<n8n-base-url>/webhook/contract-upload`

## Workflow topology

```
Webhook → Validate Input → Extract Legal Entities → Parse Risk Level → Risk Router
                                                                              │
                                              ┌───────────────────────────────┤
                                       HIGH ──┤  MEDIUM ──┤  LOW ────────────┤
                                              ▼           ▼                  ▼
                                     Slack Alert   Log Medium Risk   Persist Result
                                              │           │
                                              └───────────┴──► Persist Result
                                                                      │
                                                                      ▼
                                                             Respond to Webhook
```

## Testing with a manual POST

With the workflow active and `LEGAL_AGENT_API_URL=http://localhost:8000`, send a test
contract using curl:

```bash
curl -X POST http://localhost:5678/webhook/contract-upload \
  -H "Content-Type: application/json" \
  -d '{
    "contract_text": "MASTER SERVICES AGREEMENT\n\nThis Agreement is entered into as of January 1, 2024 by and between Acme Corp (\"Client\") and Vendor LLC (\"Vendor\").\n\nGOVERNING LAW. This Agreement is governed by the laws of the State of New York.\n\nTERMINATION FOR CONVENIENCE. Either party may terminate upon 30 days notice."
  }'
```

Expected response:
```json
{"status": "processed", "risk_level": "low", "document_name": "..."}
```

For HIGH risk testing, include a contract with no liability cap and no governing law clause.
The `Slack Escalation Alert` node will POST to your `SLACK_WEBHOOK_URL`.
