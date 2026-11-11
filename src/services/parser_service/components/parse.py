import os
from pathlib import Path

import requests
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    VlmConvertOptions,
    VlmPipelineOptions,
)
from docling.datamodel.vlm_engine_options import ApiVlmEngineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline
from dotenv import load_dotenv
from utils.logger import create_logger

logger = create_logger("parser_worker", "logs/parser_worker.log")

# Config
DATA_DIR = (
    Path("/app/data/bronze")
    if os.getenv("ENV") == "production"
    else Path("data/bronze").resolve()
)
OUTPUT_DIR = DATA_DIR.parent / "silver"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# Load and validate environment variables
load_dotenv()
PARSING_MODEL_API_KEY = os.getenv("PARSING_MODEL_API_KEY", None)
if not PARSING_MODEL_API_KEY:
    logger.error("PARSING_MODEL_API_KEY is not set in the environment.")
    raise ValueError("PARSING_MODEL_API_KEY is not set in the environment.")


# Check if OpenRouter is available
try:
    response = requests.get(
        url="https://openrouter.ai/api/v1/models",
    )
    if response.status_code != 200:
        logger.error(f"OpenRouter API returned status code {response.status_code}")
        raise ValueError("VLM/LLM service is not running properly.")
    else:
        logger.info("OpenRouter API is available.")
except Exception as e:
    logger.error(f"Error while checking OpenRouter API: {e}")
    raise ValueError("VLM/LLM service is not running.") from e

# Initialize the DocumentConverter instance
vlm_options = VlmConvertOptions.from_preset(
    "qwen",
    engine_options=ApiVlmEngineOptions(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {PARSING_MODEL_API_KEY}"},
        params={
            "model": "qwen/qwen3-vl-8b-instruct",
            "temperature": 0.0,
            "max_tokens": 8192,
        },
        concurrency=10,
        timeout=90,
    ),
)
pipeline_options = VlmPipelineOptions(
    vlm_options=vlm_options,
    enable_remote_services=True,
)
converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options,
            pipeline_cls=VlmPipeline,
        )
    }
)
logger.info("DocumentConverter initialized.")


def parse_document(relative_path: str) -> tuple[str, Path]:
    logger.info(f"Parsing document: {relative_path}")
    if not os.path.exists(relative_path):
        logger.error(f"File not found: {relative_path}")
        raise FileNotFoundError(f"File not found: {relative_path}")

    try:
        result = converter.convert(relative_path)
        md_result = result.document.export_to_markdown()
        logger.info(
            f"Document {relative_path} successfully parsed. Output has {len(md_result)} characters."
        )

        # Save the markdown result
        output_relative = Path(relative_path).relative_to(DATA_DIR)
        output_path = Path(OUTPUT_DIR) / output_relative.with_suffix(".md")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md_result, encoding="utf-8")
        logger.info(f"Markdown result saved to: {output_path}")

        return md_result, output_path

    except Exception as e:
        logger.error(f"Error while parsing document: {e}")
        raise
