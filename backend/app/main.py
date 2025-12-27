"""
Afroo Backend API - Main Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.database import connect_to_mongo, create_indexes, close_mongo_connection
from app.core.redis import connect_to_redis, close_redis_connection
from app.services.background_tasks import start_background_tasks, stop_background_tasks
from app.services.cache_service import warm_cache
from app.api.routes import (
    auth,
    users,
    # wallets,  # Old V3 wallet system - replaced by V4 crypto wallet
    exchanges,
    tickets,
    ticket_actions,
    ticket_threads,  # V4 Thread-Based Ticket System
    partners,
    admin,
    # exchanger_deposits,  # Old exchanger system - replaced by V4 with holds
    exchanger,  # V4 Exchanger System with hold logic
    holds,
    fees,
    webhooks,
    afroo_wallets,
    afroo_swaps,
    withdrawals,
    payouts,
    reputation,
    tos,
    analytics,
    ai,
    cache,
    exchanger_applications,
    key_reveals,
    support,
    escrow,
    stats,
    wallet,  # V4 Crypto Wallet System
    recovery,  # Account Recovery System
    admin_tickets,  # V4 Admin Ticket Management
    admin_users,  # V4 Admin User Management
    admin_automm_swaps,  # V4 Admin AutoMM & Swaps Management
    admin_scheduler  # V4 Admin Scheduler Management
)
from app.api.v1.endpoints import transcripts

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for FastAPI application
    Runs on startup and shutdown
    """
    # Startup
    logger.info("Starting Afroo Backend API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")

    # Connect to MongoDB
    await connect_to_mongo()
    logger.info("Connected to MongoDB")

    # Connect to Redis
    await connect_to_redis()
    logger.info("Connected to Redis")

    # Create database indexes
    await create_indexes()
    logger.info("Database indexes created")

    # Start background tasks
    start_background_tasks()
    logger.info("Background tasks started")

    # Start scheduler for periodic tasks
    from app.tasks import start_scheduler
    start_scheduler()
    logger.info("Scheduler started for periodic tasks")

    # Warm cache
    await warm_cache()
    logger.info("Cache warmed")

    yield

    # Shutdown
    logger.info("👋 Shutting down Afroo Backend API...")

    # Stop scheduler
    from app.tasks import stop_scheduler
    stop_scheduler()
    logger.info("Scheduler stopped")

    # Stop background tasks
    stop_background_tasks()
    logger.info("Background tasks stopped")

    await close_mongo_connection()
    await close_redis_connection()
    logger.info("All connections closed")


# Create FastAPI application
app = FastAPI(
    title="Afroo Exchange API",
    description="Backend API for Afroo cryptocurrency exchange platform",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "afroo-api",
        "version": "4.0.0",
        "environment": settings.ENVIRONMENT
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Afroo Exchange API",
        "version": "4.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }


# Include API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
# app.include_router(wallets.router, prefix="/api/v1/wallets", tags=["Wallets"])  # Old V3 - replaced by V4
app.include_router(exchanges.router, prefix="/api/v1/exchanges", tags=["Exchanges"])
app.include_router(tickets.router, prefix="/api/v1/tickets", tags=["Tickets"])
app.include_router(ticket_actions.router, prefix="/api/v1/tickets", tags=["Ticket Actions"])
app.include_router(ticket_threads.router, prefix="/api/v1/ticket-threads", tags=["Ticket Threads V4"])
app.include_router(partners.router, prefix="/api/v1/partners", tags=["Partners"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(admin_tickets.router, prefix="/api/v1/admin", tags=["Admin - Tickets"])
app.include_router(admin_users.router, prefix="/api/v1/admin", tags=["Admin - Users"])
app.include_router(admin_automm_swaps.router, prefix="/api/v1/admin", tags=["Admin - AutoMM & Swaps"])
app.include_router(admin_scheduler.router, tags=["Admin - Scheduler"])

# V3 Core System Routes
# app.include_router(exchanger_deposits.router, prefix="/api/v1", tags=["Exchanger Deposits"])  # OLD - replaced by V4
app.include_router(exchanger.router, tags=["Exchanger V4"])  # V4 Exchanger with hold logic
app.include_router(holds.router, prefix="/api/v1", tags=["Holds"])
app.include_router(fees.router, prefix="/api/v1", tags=["Fee Collection"])
app.include_router(webhooks.router, prefix="/api/v1", tags=["Webhooks"])

# V4 New Features
app.include_router(wallet.router, prefix="/api/v1", tags=["Crypto Wallet V4"])
app.include_router(afroo_wallets.router, prefix="/api/v1", tags=["Afroo Wallets"])
app.include_router(afroo_swaps.router, prefix="/api/v1", tags=["Afroo Swaps"])
app.include_router(withdrawals.router, prefix="/api/v1", tags=["Withdrawals"])
app.include_router(reputation.router, prefix="/api/v1", tags=["Reputation"])
app.include_router(tos.router, prefix="/api/v1", tags=["Terms of Service"])
app.include_router(ai.router, prefix="/api/v1", tags=["AI Assistant"])

# Transcript System (Upload + View)
app.include_router(transcripts.router, prefix="/api/v1/transcripts", tags=["Transcripts - Upload"])
app.include_router(transcripts.router, prefix="/transcripts", tags=["Transcripts - Public View"])

# Admin Routes
app.include_router(payouts.router, prefix="/api/v1", tags=["Payouts (Admin)"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics (Admin)"])
app.include_router(cache.router, prefix="/api/v1", tags=["Cache (Admin)"])

# Exchanger Features
app.include_router(exchanger_applications.router, prefix="/api/v1", tags=["Exchanger Applications"])
app.include_router(key_reveals.router, prefix="/api/v1", tags=["Key Reveals"])

# Support & Community Features
app.include_router(support.router, prefix="/api/v1", tags=["Support"])
app.include_router(escrow.router, prefix="/api/v1", tags=["Escrow"])
app.include_router(stats.router, prefix="/api/v1", tags=["Statistics"])

# Account Recovery
app.include_router(recovery.router, prefix="/api/v1", tags=["Account Recovery"])


# Global exception handler
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions"""
    logger.error(f"ValueError: {exc}", exc_info=True)
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle all unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "type": "internal_error"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
