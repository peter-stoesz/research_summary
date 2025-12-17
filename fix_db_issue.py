#!/usr/bin/env python3
"""
Quick fix for the dict adaptation issue in PostgreSQL.
This script will help identify and fix the database compatibility issue.
"""

import os
import sys
from pathlib import Path

# Add the project to Python path
sys.path.insert(0, str(Path(__file__).parent))

from aipod.config import Config, load_sources
from aipod.db import get_connection
import json

def test_database_operations():
    """Test database operations to identify the dict issue."""
    print("🔧 Testing database operations...")
    
    # Load config
    config = Config()
    db_config = config.get_db_config()
    
    try:
        with get_connection(db_config) as conn:
            with conn.cursor() as cur:
                print("✅ Database connection successful")
                
                # Test simple query
                cur.execute("SELECT 1 as test")
                result = cur.fetchone()
                print(f"✅ Simple query works: {result}")
                
                # Test sources operations
                sources_path = config.config_path.parent / "sources.yaml"
                sources = load_sources(sources_path)
                print(f"✅ Loaded {len(sources)} sources")
                
                # Test source insertion (this is likely where the error occurs)
                for i, source in enumerate(sources[:2]):  # Test first 2 sources only
                    print(f"Testing source {i+1}: {source.name}")
                    
                    # Convert Pydantic model to plain values
                    cur.execute(
                        """
                        INSERT INTO sources (name, url, category, weight, enabled)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (name) DO UPDATE SET
                            url = EXCLUDED.url,
                            category = EXCLUDED.category,
                            weight = EXCLUDED.weight,
                            enabled = EXCLUDED.enabled
                        RETURNING id
                        """,
                        (
                            source.name,
                            source.url,
                            source.category,
                            float(source.weight),  # Ensure it's a Python float
                            bool(source.enabled),  # Ensure it's a Python bool
                        ),
                    )
                    
                    source_id = cur.fetchone()["id"]
                    print(f"✅ Source inserted with ID: {source_id}")
                
                # Test JSON operations (another potential issue)
                test_json = {"test": "value", "number": 123}
                cur.execute(
                    "SELECT %s::jsonb as test_json",
                    (json.dumps(test_json),)
                )
                result = cur.fetchone()
                print(f"✅ JSON operations work: {result}")
                
                conn.commit()
                print("✅ All database tests passed!")
                return True
                
    except Exception as e:
        print(f"❌ Database error: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run database tests and fixes."""
    print("🎙️ AI Podcast Agent - Database Fix Tool\n")
    
    # Test if environment variables are set
    if not os.environ.get("AIPOD_DB_PASSWORD"):
        print("❌ AIPOD_DB_PASSWORD not set!")
        print("Run: source .env")
        return False
    
    print("✅ Environment variables loaded")
    
    # Run tests
    if test_database_operations():
        print("\n🎉 Database tests passed! You can now run the pipeline:")
        print("python3 -m aipod.cli.app run --minutes 3 --max-items 5 --max-stories 2")
        return True
    else:
        print("\n❌ Database tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)