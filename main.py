# main.py
"""
Main entry point for QUANT EDGE PRO
Orchestrates WebSocket server and trading engine
"""
import asyncio
import logging
from api.server import QuantEdgeServer
from agents.ensemble import EnsembleTrader
from core.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main async entry point"""
    config = get_config()
    
    logger.info("="*60)
    logger.info("QUANT EDGE PRO - Institutional Trading Terminal")
    logger.info("="*60)
    logger.info(f"CUDA Enabled: {config.cuda.enabled}")
    logger.info(f"Device: {config.cuda.device}")
    logger.info(f"Assets: {', '.join(config.assets)}")
    logger.info(f"API Server: ws://{config.api_host}:{config.api_port}")
    logger.info("="*60)
    
    # Create and start server
    server = QuantEdgeServer(
        host=config.api_host,
        port=config.api_port
    )
    
    logger.info(f"Starting WebSocket server on ws://{config.api_host}:{config.api_port}")
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")

def run_sync():
    """Synchronous wrapper for main"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")

if __name__ == "__main__":
    run_sync()
