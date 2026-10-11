"""Speech-to-USSD — Entry point."""

from src.daraja import (
    stk_push,
    register_c2b_urls,
    b2c_payment,
    transaction_status_query,
    initiate_c2c_transfer,
    continue_c2c_transfer,
    initiate_direct_b2c,
    initiate_direct_c2b,
)
from src.pipeline import run_pipeline
from app.interface import cli

if __name__ == "__main__":
    cli() 
