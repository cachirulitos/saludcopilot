# TASK.md — ml/

> Read CLAUDE.md and ARQUITECTURA.md before starting.
> The trained model is imported by the API at startup.
> Coordinate with Dev 1 (API) on Task 4 — they need to know
> the exact import path and class interface before integrating.

---

## Current status

- [x] Project scaffold created
- [x] requirements.txt
- [ ] Data loading and validation
- [ ] Feature engineering pipeline
- [ ] Model training and serialization
- [ ] Inference class
- [ ] Training notebook with evaluation plots

---

## What this module does — read this first

This module trains a Random Forest Regressor that predicts wait time
in minutes per clinical area, based on historical data from Salud Digna's Excel.

**Training happens before the hackathon demo.**
**Inference happens at runtime inside the API process.**

The model is NOT a web service. It is a Python module imported by the API.
After training, two files are saved to `ml/models/`: `model.pkl` and `encodings.pkl`.
The API loads them once at startup via `WaitTimePredictor` and reuses the instance.

---

## Task 1 — Data loading and validation

Create `ml/src/data_loader.py`.

**Place these CSVs in `ml/data/` before running (export from Excel):**
- `ventas.csv` — from Ventas sheet
- `promedios_espera.csv` — from Promedios de Espera sheet
- `consultorios.csv` — from Consultorios x Clínica sheet
- `prioridad.csv` — from Prioridad Atención sheet

```python
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"

def load_ventas() -> pd.DataFrame:
    """
    Load Ventas sheet.
    Required columns: idSucursal, idEstudio, idPaciente,
                      FechaServicio, Estatus, idReservacion
    Parses FechaServicio as datetime — must include time component.
    Drops rows where FechaServicio is null. Logs row count before/after.
    """

def load_promedios_espera() -> pd.DataFrame:
    """
    Load Promedios de Espera sheet.
    Required columns: idSucursal, idEstudio, Promedio, Fecha
    Promedio is the target variable: wait time in minutes.
    """

def load_consultorios() -> pd.DataFrame:
    """
    Load Consultorios x Clínica sheet.
    Required columns: idSucursal, idEstudio, CantidadConsultorios
    """

def validate_dataframe(
    df: pd.DataFrame,
    required_columns: list[str],
    name: str,
) -> None:
    """
    Raise ValueError with exact missing column name if any required
    column is absent. Log shape and null count per required column.
    """
```

**Acceptance criteria:**
- All loaders run without error on real CSV files
- `validate_dataframe` raises `ValueError("Missing column: [name] in [sheet]")`
- `FechaServicio` dtype is datetime64 after loading
- Row counts logged before and after any filtering — nothing dropped silently

---

## Task 2 — Feature engineering pipeline

Create `ml/src/feature_engineering.py`.

**Target variable:** `waiting_time_minutes` from `promedios_espera.csv` → `Promedio`

```python
import pandas as pd

def build_training_features(
    ventas: pd.DataFrame,
    promedios: pd.DataFrame,
    consultorios: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """
    Join and transform raw data into model-ready features.
    Returns (features_df, encoding_maps).

    Features to produce:
    - hour_of_day: int (0-23) from FechaServicio
    - day_of_week: int (0=Monday, 6=Sunday) from FechaServicio
    - is_weekend: int (0 or 1)
    - study_type_id: int — label encoded from idEstudio
    - clinic_id: int — label encoded from idSucursal
    - simultaneous_capacity: int — from consultorios joined on idSucursal+idEstudio
    - current_queue_length: int — approximated from ventas as concurrent visits
    - has_appointment: int (0 or 1) — 1 if idReservacion not null/empty

    Target column:
    - waiting_time_minutes: float — from Promedio joined on idSucursal+idEstudio+date

    Drop rows where waiting_time_minutes is null. Log count dropped.

    encoding_maps format:
    {
      "study_type": {"raw_id_value": encoded_int, ...},
      "clinic": {"raw_id_value": encoded_int, ...}
    }
    """

def extract_inference_features(
    hour_of_day: int,
    day_of_week: int,
    study_type_raw_id: str | int,
    clinic_raw_id: str | int,
    simultaneous_capacity: int,
    current_queue_length: int,
    has_appointment: bool,
    encoding_maps: dict,
) -> pd.DataFrame:
    """
    Build a single-row DataFrame for runtime inference.
    Applies label encoding using saved encoding_maps.
    Feature column order must match build_training_features exactly.
    Returns single-row DataFrame — same schema as training output.
    """
```

**Critical:** feature column order must be identical between
`build_training_features` and `extract_inference_features`.
Define the column list as a module-level constant and use it in both functions.

```python
FEATURE_COLUMNS = [
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "study_type_id",
    "clinic_id",
    "simultaneous_capacity",
    "current_queue_length",
    "has_appointment",
]
```

**Acceptance criteria:**
- Returns DataFrame with exactly 8 feature columns + `waiting_time_minutes`
- No nulls in any feature column after pipeline
- `extract_inference_features` produces one-row DataFrame with same column order
- Test verifies `FEATURE_COLUMNS` is identical in both output DataFrames

---

## Task 3 — Model training and serialization

Create `ml/src/train.py`.

```python
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import pandas as pd

HYPERPARAMETERS = {
    "n_estimators": 100,
    "max_depth": None,
    "min_samples_split": 2,
    "random_state": 42,
    "n_jobs": -1,
}

def train_model(
    features_df: pd.DataFrame,
) -> tuple[RandomForestRegressor, dict]:
    """
    Train Random Forest on prepared features.
    Returns (trained_model, metrics_dict).

    Steps:
    1. Separate features (FEATURE_COLUMNS) and target (waiting_time_minutes)
    2. Train/test split: test_size=0.2, random_state=42
    3. Train RandomForestRegressor(**HYPERPARAMETERS)
    4. Evaluate on test set
    5. Log: "MAE: X.X min | R2: X.XX | Training samples: N | Test samples: N"
    6. Return model and metrics
    """

def save_artifacts(
    model: RandomForestRegressor,
    encoding_maps: dict,
    output_dir: Path,
) -> None:
    """
    Save model and encodings to output_dir.
    Creates output_dir if it does not exist.
    Saves:
    - model.pkl (joblib)
    - encodings.pkl (joblib)
    Logs full paths of saved files.
    """

def load_artifacts(model_dir: Path) -> tuple[RandomForestRegressor, dict]:
    """
    Load model and encodings from disk.
    Raises FileNotFoundError with clear message if either file missing.
    """
```

**Acceptance criteria:**
- Training completes on real data without error
- Metrics logged in exact format: "MAE: X.X min | R2: X.XX"
- Both `.pkl` files saved to `ml/models/`
- `load_artifacts` round-trip works: save then load returns same model
- Test in `tests/test_train.py` trains on 20 synthetic rows and verifies
  save/load cycle produces identical predictions

---

## Task 4 — Inference class (API imports this)

Create `ml/src/predictor.py`.

```python
from pathlib import Path
import pandas as pd

MODEL_DIR = Path(__file__).parent.parent / "models"

class WaitTimePredictor:
    """
    Loads trained model once and exposes predict_wait_minutes.
    Instantiate once at API startup. Reuse for all predictions.
    Thread-safe for concurrent requests.
    """

    def __init__(self, model_dir: Path = MODEL_DIR) -> None:
        """
        Load model and encodings from model_dir.
        Raises FileNotFoundError with clear message if model not trained yet.
        """

    def predict_wait_minutes(
        self,
        hour_of_day: int,
        day_of_week: int,
        study_type_raw_id: str | int,
        clinic_raw_id: str | int,
        simultaneous_capacity: int,
        current_queue_length: int,
        has_appointment: bool,
    ) -> int:
        """
        Predict wait time in minutes.
        Returns int >= 1. Never returns 0 or negative.

        Unseen labels (study_type or clinic not in training data):
        use median wait time from training as fallback.
        Log warning: "Unknown study_type_id {X} — using median fallback"
        """

    @property
    def is_ready(self) -> bool:
        """Returns True if model loaded successfully."""
```

**How the API will import this:**
```python
# Dev 1 adds to apps/api/app/core/predictor_client.py
import sys
sys.path.insert(0, "/ml")
from src.predictor import WaitTimePredictor
predictor = WaitTimePredictor()
```

**Acceptance criteria:**
- Loads model in `__init__` with no side effects on import
- `predict_wait_minutes` always returns int >= 1
- Unseen labels use fallback without raising
- `is_ready` returns False if model files not found (no crash)
- Test verifies return type is always int >= 1 for any valid input

---

## Task 5 — Training notebook

Create `ml/notebooks/train_and_evaluate.ipynb`.

**Sections:**
1. Load raw data (use `data_loader` functions)
2. Feature engineering (use `feature_engineering` functions)
3. Train model (use `train_model`)
4. Evaluation:
   - Feature importance bar chart (horizontal, sorted descending)
   - Predicted vs actual scatter plot on test set (with diagonal reference line)
   - Wait time distribution by `hour_of_day` (box plot)
5. Save artifacts (use `save_artifacts`)
6. Final cell output:
   ```
   Model saved to ml/models/
   MAE: X.X min | R2: X.XX
   Ready for inference.
   ```

**Acceptance criteria:**
- Notebook runs top to bottom without errors on real data
- All three plots render inline with titles and axis labels
- Final cell prints the exact format above

---

## Output files after training

```
ml/
├── models/
│   ├── model.pkl
│   └── encodings.pkl
└── notebooks/
    └── train_and_evaluate.ipynb
```

`ml/models/` is in `.gitignore`. For the hackathon demo,
commit the model files directly so the API can load them at startup.
Remove the `ml/models/` line from `.gitignore` before the final commit.

---

## Do not implement yet

- Automated retraining pipeline
- Model versioning or rollback
- Confidence intervals on predictions
- Online learning or incremental updates
