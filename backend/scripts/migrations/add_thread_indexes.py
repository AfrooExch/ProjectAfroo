"""
MongoDB Migration: Add Thread System Indexes
Creates indexes for the new thread-based ticket system
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
if not MONGODB_URL:
    raise ValueError("MONGODB_URL environment variable is required")


async def create_thread_indexes():
    """Create indexes for thread-based ticket system"""
    print("Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client.get_default_database()
    tickets_collection = db["tickets"]

    print("\nCreating indexes for thread system...")

    # Index for client thread lookups
    print("Creating index: client_thread_id")
    await tickets_collection.create_index("client_thread_id", name="idx_client_thread_id")

    # Index for exchanger thread lookups
    print("Creating index: exchanger_thread_id")
    await tickets_collection.create_index("exchanger_thread_id", name="idx_exchanger_thread_id")

    # Index for hold status filtering
    print("Creating index: hold_status")
    await tickets_collection.create_index("hold_status", name="idx_hold_status")

    # Compound index for status + created_at (for efficient queue queries)
    print("Creating compound index: status + created_at")
    await tickets_collection.create_index(
        [("status", 1), ("created_at", -1)],
        name="idx_status_created_at"
    )

    # Index for channel_id (legacy system - for migration)
    print("Creating index: channel_id (legacy)")
    await tickets_collection.create_index("channel_id", name="idx_channel_id")

    print("\n✅ All indexes created successfully!")

    # List all indexes
    print("\nCurrent indexes on tickets collection:")
    indexes = await tickets_collection.list_indexes().to_list(length=None)
    for idx in indexes:
        print(f"  - {idx['name']}: {idx.get('key', {})}")

    client.close()


async def main():
    """Main execution"""
    print("=" * 60)
    print("MongoDB Thread System Index Migration")
    print("=" * 60)

    try:
        await create_thread_indexes()
        print("\n✅ Migration completed successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
