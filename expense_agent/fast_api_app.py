import logging

from google.adk.cli.fast_api import get_fast_api_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = get_fast_api_app(
    agents_dir="expense_agent",
    web=False,
    trigger_sources=["pubsub"],
    otel_to_cloud=False,
    auto_create_session=True,
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
