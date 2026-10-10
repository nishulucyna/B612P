"""Print the names of required Python packages that are not installed (empty output = all present)."""

import importlib.util

REQUIRED = ["fastapi", "uvicorn", "streamlit", "requests", "sounddevice", "pyttsx3", "pydantic", "multipart"]
print(" ".join(m for m in REQUIRED if importlib.util.find_spec(m) is None))
