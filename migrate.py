"""Database migration CLI entrypoint for OnBoarding Buddy."""
import logging
import sys
from database import init_db, run_migrations

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("migrate")

if __name__ == "__main__":
    logger.info("Initializing database and applying schema migrations...")
    try:
        init_db()
        logger.info("Database successfully migrated and synchronized with models.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)
