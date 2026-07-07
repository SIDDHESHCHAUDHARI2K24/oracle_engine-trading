# Google Colab Training Runbook

How to export the feature matrix, train a universe model on Google Colab's GPU, download
artifacts, and register them back into the local pipeline. Use when the local machine lacks a GPU
or you want to leverage Colab's T4/A100 for faster training.

---

## Prerequisites

- Google Drive account with enough space (model artifacts are typically 200-500 MB per universe)
- Google Colab access
- The Oracle Engine backend repo cloned locally
- Feature matrix materialized in the local TimescaleDB (run feature engineering first)

---

## Step 1: Export the Feature Matrix

From your local machine, dump the feature matrix rows for the target universe:

```bash
cd backend

# Export feature_matrix rows for universe to a compressed CSV
uv run python scripts/export_feature_matrix.py \
  --universe sp500 \
  --output ~/colab_exports/sp500_features.parquet \
  --format parquet
```

The script joins `feature_matrix` with `universe_memberships` to scope rows to active tickers in the
target universe. Output is a single Parquet file with columns: `ticker_id`, `bar_date`, all 31
feature columns, and all 4 target columns.

If the script doesn't exist yet, use the raw SQL approach:

```bash
psql -U mbi_user -d mbi -p 5433 -c "\copy (
  SELECT fm.* FROM feature_matrix fm
  JOIN universe_memberships um ON fm.ticker_id = um.ticker_id
  WHERE um.universe_id = '<UNIVERSE_UUID>' AND um.removed_at IS NULL
  ORDER BY fm.bar_date
) TO '/tmp/sp500_features.csv' WITH CSV HEADER"
```

---

## Step 2: Upload the Export to Google Drive

```bash
# If you have gdrive CLI or just upload via the web UI
# Place it in a folder like: MBI/colab_exports/
```

Or upload directly from Colab in the next step.

---

## Step 3: Mount Google Drive in Colab

Open a new Colab notebook at https://colab.research.google.com, then:

```python
from google.colab import drive
drive.mount('/content/drive')
```

---

## Step 4: Install Dependencies in Colab

```python
!pip install torch pytorch-lightning pytorch-forecasting scipy scikit-learn pandas numpy

# Install the Oracle Engine backend as an editable package
!git clone https://github.com/<your-org>/oracle-engine-trading.git /content/oracle-engine
!pip install -e /content/oracle-engine/backend
```

---

## Step 5: Load the Feature Matrix

```python
import pandas as pd

df = pd.read_parquet('/content/drive/MyDrive/MBI/colab_exports/sp500_features.parquet')
print(f"Loaded {len(df)} rows, {df['ticker_id'].nunique()} tickers")
print(f"Date range: {df['bar_date'].min()} to {df['bar_date'].max()}")
```

---

## Step 6: Run train_universe()

```python
import uuid
from datetime import date

from app.features.ml_models.service import train_universe
from app.features.core.database import async_session_factory
from app.core.services.artifact_store import LocalArtifactStore

UNIVERSE_ID = uuid.UUID("...")  # Replace with your actual universe UUID

async def train():
    store = LocalArtifactStore(base_path="/content/drive/MyDrive/MBI/artifacts")

    async with async_session_factory() as session:
        result = await train_universe(
            universe_id=UNIVERSE_ID,
            as_of_date=date.today(),
            db_session=session,
            artifact_store=store,
        )
        print(f"Training complete: {result.status}")
        print(f"Training run ID: {result.training_run_id}")
        print(f"Artifact IDs: {result.artifact_ids}")
        print(f"Validation metrics: {result.validation_metrics}")
        return result

import asyncio
result = await train()
```

**Training time estimates on Colab**:

| GPU | S&P 500 (~500 tickers) | Russell 1000 (~1000) | Russell 2000 (~2000) |
|---|---|---|---|
| T4 (free) | ~15-20 min | ~30-40 min | ~1-1.5 hr |
| A100 (Pro) | ~5-8 min | ~10-15 min | ~20-30 min |

---

## Step 7: Download Artifacts Back to Local

### Option A: Save to Google Drive, Download Later

Artifacts are already saved to `/content/drive/MyDrive/MBI/artifacts/` if you pointed
`LocalArtifactStore` there. Download them from Google Drive web UI.

### Option B: Direct Download

```python
import os
import shutil

# Zip the artifacts directory
artifact_dir = "/content/drive/MyDrive/MBI/artifacts"
shutil.make_archive("/content/artifacts_export", 'zip', artifact_dir)

# Download via Colab's file browser or:
from google.colab import files
files.download("/content/artifacts_export.zip")
```

---

## Step 8: Register Artifacts on Local Machine

Copy the downloaded artifacts to the local artifact store:

```bash
# On your local machine
mkdir -p ~/.mbi/artifacts/
cp ~/Downloads/artifacts_export/* ~/.mbi/artifacts/
```

Then register the Colab-trained artifacts in the local database:

```bash
cd backend
uv run python scripts/register_artifacts.py \
  --training-run-id <UUID from Colab output> \
  --artifact-dir ~/.mbi/artifacts/
```

This updates the `model_artifacts` and `training_runs` tables so the local inference pipeline
uses the Colab-trained models.

---

## Step 9: Verify

```bash
# Check that artifacts are registered and active
curl -s http://localhost:8000/api/v1/monitoring/health/{universe_id} | python -m json.tool | grep -A5 active_artifacts
```

Trigger an inference run to confirm the new models work:

```bash
curl -X POST http://localhost:8000/api/v1/ml_models/trigger_inference?universe_id=<id>
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Out of memory on T4 | Reduce batch size in training config; reduce `num_layers` from 3 to 2 |
| `train_universe` not found | Verify `pip install -e` ran without errors; check `sys.path` |
| Parquet read fails | Column name mismatch — Colab pandas may be newer; use `pip install pandas==2.x` |
| Colab runtime disconnects | T4 free tier disconnects after ~90 min idle. Keep a cell running with `while True: pass` during long trains |
| Artifact files missing locally | The Colab `LocalArtifactStore` may have written to ephemeral storage; always point it at `/content/drive/...` |
