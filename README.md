# Cognigy project repository sync

This repository is set up to download and upload major Cognigy project elements.

## Included element folders

- `elements/project_metadata`
- `elements/ai_agents`
- `elements/flows`
- `elements/flow_charts`
- `elements/intents`
- `elements/example_sentences`
- `elements/endpoints`
- `elements/lexicons`
- `snapshots/` for timestamped backups before uploads

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Confirm `.env` is present at repository root.

## Usage

Download current project assets into `elements/`:

```bash
python scripts/cognigy_sync.py download
```

Create only a backup snapshot:

```bash
python scripts/cognigy_sync.py backup
```

Upload local assets from `elements/` back to Cognigy **after backup is automatically created**:

```bash
python scripts/cognigy_sync.py upload
```

You can override source/destination roots:

```bash
python scripts/cognigy_sync.py download --destination /tmp/cognigy-export
python scripts/cognigy_sync.py upload --source /tmp/cognigy-export
```

## Notes

- Upload uses `PUT` for each element category.
- If a local element file is missing during upload, it is skipped.
- API endpoints can be adjusted in `scripts/cognigy_sync.py` under `RESOURCE_MAP`.
