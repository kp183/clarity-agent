import uvicorn
# Correctly import the server instance and settings from their package locations
from .tools import mcp_server
from ..config.settings import settings
from ..utils.logging import logger

def start_mcp_server():
    """
    Starts the MCP server with all registered tools using Uvicorn.
    This is a synchronous, blocking function.
    """
    try:
        logger.info("Starting MCP server...", 
                   host=settings.mcp_server_host, 
                   port=settings.mcp_server_port)
        
        # Use uvicorn to run the FastAPI/FastMCP application instance
        uvicorn.run(
            mcp_server,
            host=settings.mcp_server_host,
            port=settings.mcp_server_port,
            log_level="info"  # Controls uvicorn's own logging level
        )
        
    except Exception as e:
        logger.error("Failed to start MCP server", error=str(e))
        # Re-raise the exception to make the application exit on a critical error
        raise

# This block allows you to run this script directly for testing purposes
# e.g., `python -m clarity_agent.mcp_server.server`
if __name__ == "__main__":
    try:
        start_mcp_server()
    except KeyboardInterrupt:
        logger.info("MCP Server shut down by user.")