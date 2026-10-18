import os
import time
from fastapi import FastAPI, Request
from fastapi.responses import Response
import joblib
import pandas as pd
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# ==========================================
# APP
# ==========================================

app = FastAPI(
    title="AQI Prediction API",
    description="API for AQI prediction using Machine Learning",
    version="1.0"
)

# ==========================================
# PROMETHEUS METRICS INSTRUMENTATION
# ==========================================

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP Request Latency in seconds",
    ["method", "endpoint"]
)

PREDICTION_COUNT = Counter(
    "aqi_predictions_total",
    "Total AQI Predictions categorized by outcome",
    ["category"]
)

APP_INFO = Gauge(
    "app_info",
    "Application metadata",
    ["version", "framework"]
)
APP_INFO.labels(version="1.0", framework="fastapi").set(1)

@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start_time = time.time()
    method = request.method
    endpoint = request.url.path

    response = await call_next(request)

    duration = time.time() - start_time
    status = str(response.status_code)

    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

    return response

# ==========================================
# PATHS
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")

# ==========================================
# LOAD MODELS
# ==========================================

classifier = joblib.load(
    os.path.join(MODEL_DIR, "random_forest_classifier.joblib")
)

regressor = joblib.load(
    os.path.join(MODEL_DIR, "aqi_regression_model.joblib")
)

label_encoder = joblib.load(
    os.path.join(MODEL_DIR, "aqi_label_encoder.joblib")
)

features = joblib.load(
    os.path.join(MODEL_DIR, "aqi_features.joblib")
)

# ==========================================
# HEALTH & HOME ROUTES
# ==========================================

@app.get("/")
def home():
    return {
        "message": "AQI Prediction API is running!",
        "features": features
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "aqi-prediction-api"
    }

# ==========================================
# PROMETHEUS METRICS ENDPOINT
# ==========================================

@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# ==========================================
# AQI PREDICTION
# ==========================================

@app.post("/predict-aqi")
def predict_aqi(data: dict):

    # Create input DataFrame
    input_data = pd.DataFrame(
        [[data[feature] for feature in features]],
        columns=features
    )

    # AQI prediction
    predicted_aqi = regressor.predict(input_data)[0]

    # Category prediction
    predicted_class = classifier.predict(input_data)[0]

    predicted_category = label_encoder.inverse_transform(
        [predicted_class]
    )[0]

    PREDICTION_COUNT.labels(category=predicted_category).inc()

    return {
        "predicted_aqi": round(float(predicted_aqi), 2),
        "category": predicted_category
    }