"""
src - A document processing toolkit for converting DOCX and PDF files to structured data.

This package provides tools for:
- Converting DOCX files to TXT format
- Converting PDF files to TXT format
- Processing documents through AI-powered pipelines
- Document retrieval and search functionality
"""

from pathlib import Path
from typing import Optional

# 使用相对导入，因为 pipeline 现在在同一个包内
from .pipeline.main import run_pipeline

__version__ = "0.1.0"


def process_document(
    file_path: str,
    base_url: str = "https://api.openai.com/v1",
    api_key: str = "sk-your-api-key-here",
    model: str = "gpt-4",
    prompt_file: Optional[str] = None,
    sample_chars: int = 500,
    sample_chars_max: int = 8000,
    output_dir: Optional[str] = None,
    timeout: int = 120,
    max_depth: int = 1,
    max_file_length: int = 0,
    regex_config_file: Optional[str] = None
):
    """
    Process a single document file (DOCX or PDF) through the complete pipeline.
    
    This function converts the document to TXT format and then recursively splits it
    using AI-generated regular expressions. It does not require a config file and
    accepts all parameters directly.
    
    Args:
        file_path: Path to the document file (supports .docx or .pdf)
        base_url: OpenAI API base URL (e.g., https://api.openai.com/v1 or http://localhost:8000/v1).
                  Default: "https://api.openai.com/v1"
        api_key: API key for OpenAI API (can be any value for local models).
                 Default: "sk-your-api-key-here"
        model: Model name (e.g., gpt-4, gpt-3.5-turbo, or custom model name).
               Default: "gpt-4"
        prompt_file: Path to prompt template file. If None, uses default path (prompt/prompt_select)
        sample_chars: Number of sample characters to extract, default 500
        sample_chars_max: Maximum number of sample characters, default 8000
        output_dir: Output directory. If None, creates a folder with the same name as the input file
        timeout: API call timeout in seconds, default 120
        max_depth: Maximum recursion depth, default 1
        max_file_length: Maximum sub-file length in characters, default 0 (no limit).
                        Files with length <= this value will skip splitting
        regex_config_file: Path to regex pattern configuration file.
                          If None, uses default path (config/regex_patterns.py)
    
    Returns:
        None (processes the document and saves output files)
    
    Raises:
        SystemExit: If file does not exist, format is unsupported, or processing fails
    
    Example:
        ```python
        from src import process_document
        
        process_document(
            file_path="document.pdf",
            output_dir="./output",
            max_depth=3
        )
        
        # Or with custom API settings:
        process_document(
            file_path="document.pdf",
            base_url="https://api.openai.com/v1",
            api_key="sk-your-api-key",
            model="gpt-4",
            output_dir="./output"
        )
        ```
    """
    # Set default prompt file path if not provided
    if prompt_file is None:
        # pipeline 现在在同一个包内
        pipeline_dir = Path(__file__).parent / "pipeline"
        prompt_file = str(pipeline_dir / "prompt" / "prompt_select")
    
    # Set default regex config file path if not provided
    if regex_config_file is None:
        # pipeline 现在在同一个包内
        pipeline_dir = Path(__file__).parent / "pipeline"
        regex_config_file = str(pipeline_dir / "config" / "regex_patterns.py")
    
    run_pipeline(
        file_path=file_path,
        base_url=base_url,
        api_key=api_key,
        model=model,
        prompt_file=prompt_file,
        sample_chars=sample_chars,
        sample_chars_max=sample_chars_max,
        output_dir=output_dir,
        timeout=timeout,
        max_depth=max_depth,
        max_file_length=max_file_length,
        regex_config_file=regex_config_file
    )

