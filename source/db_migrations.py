"""
Database migration system for HackFlix

Handles schema versioning and safe migrations between versions.
Each migration is a Python function that modifies the database schema.

Usage:
    from db_migrations import migrate_database
    migrate_database()  # Automatically migrates to latest version
"""

import sqlite3
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime

from db_schema import DATABASE_VERSION, DEFAULT_DATABASE_FILE


# Migration history: version -> migration function
MIGRATIONS = {}


def migration(from_version: int, to_version: int):
    """
    Decorator to register a migration function

    Example:
        @migration(from_version=1, to_version=2)
        def add_rating_field(conn):
            conn.execute("ALTER TABLE movies ADD COLUMN rating REAL")
    """
    def decorator(func: Callable):
        MIGRATIONS[(from_version, to_version)] = func
        return func
    return decorator


def get_current_version(conn: sqlite3.Connection) -> int:
    """
    Get current database version

    Args:
        conn: Database connection

    Returns:
        Current version number (0 if not set)
    """
    try:
        cursor = conn.execute("SELECT value FROM metadata WHERE key = 'db_version'")
        result = cursor.fetchone()
        return int(result[0]) if result else 0
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        return 0


def set_version(conn: sqlite3.Connection, version: int) -> None:
    """
    Update database version in metadata

    Args:
        conn: Database connection
        version: New version number
    """
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("db_version", str(version))
    )
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("last_migration", datetime.now().isoformat())
    )


def create_migration_log_table(conn: sqlite3.Connection) -> None:
    """
    Create table to track migration history

    Args:
        conn: Database connection
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS migration_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_version INTEGER NOT NULL,
            to_version INTEGER NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN DEFAULT TRUE,
            error_message TEXT
        )
    """)


def log_migration(
    conn: sqlite3.Connection,
    from_version: int,
    to_version: int,
    success: bool = True,
    error_message: Optional[str] = None
) -> None:
    """
    Log a migration execution

    Args:
        conn: Database connection
        from_version: Starting version
        to_version: Target version
        success: Whether migration succeeded
        error_message: Error details if failed
    """
    conn.execute(
        """
        INSERT INTO migration_log (from_version, to_version, success, error_message)
        VALUES (?, ?, ?, ?)
        """,
        (from_version, to_version, success, error_message)
    )


def get_migration_path(current: int, target: int) -> list:
    """
    Find sequence of migrations to apply

    Args:
        current: Current database version
        target: Target version

    Returns:
        List of (from_version, to_version) tuples
    """
    if current >= target:
        return []

    # Simple sequential path (v1 -> v2 -> v3 -> ...)
    path = []
    version = current
    while version < target:
        next_version = version + 1
        if (version, next_version) not in MIGRATIONS:
            raise ValueError(
                f"No migration found from version {version} to {next_version}"
            )
        path.append((version, next_version))
        version = next_version

    return path


def migrate_database(
    db_path: Optional[str] = None,
    target_version: Optional[int] = None,
    dry_run: bool = False
) -> bool:
    """
    Migrate database to target version

    Args:
        db_path: Path to database file (default: hackflix.db)
        target_version: Version to migrate to (default: latest)
        dry_run: If True, only print what would be done

    Returns:
        True if migration successful, False otherwise
    """
    if db_path is None:
        db_path = DEFAULT_DATABASE_FILE

    if target_version is None:
        target_version = DATABASE_VERSION

    if not Path(db_path).exists():
        print(f"❌ Database does not exist: {db_path}")
        print("   Run: python source/db_schema.py --init")
        return False

    conn = sqlite3.connect(db_path)

    try:
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")

        # Create migration log table
        create_migration_log_table(conn)

        # Get current version
        current_version = get_current_version(conn)

        print(f"📊 Current database version: {current_version}")
        print(f"🎯 Target version: {target_version}")

        if current_version >= target_version:
            print("✅ Database is already at target version")
            return True

        # Find migration path
        try:
            migration_path = get_migration_path(current_version, target_version)
        except ValueError as e:
            print(f"❌ {e}")
            return False

        print(f"📋 Migrations to apply: {len(migration_path)}")

        if dry_run:
            print("\n🔍 DRY RUN - No changes will be made:")
            for from_ver, to_ver in migration_path:
                migration_func = MIGRATIONS[(from_ver, to_ver)]
                print(f"   {from_ver} -> {to_ver}: {migration_func.__name__}")
            return True

        # Apply migrations
        for from_ver, to_ver in migration_path:
            migration_func = MIGRATIONS[(from_ver, to_ver)]

            print(f"\n🔄 Applying migration {from_ver} -> {to_ver}...")
            print(f"   Function: {migration_func.__name__}")

            try:
                # Start transaction
                conn.execute("BEGIN")

                # Apply migration
                migration_func(conn)

                # Update version
                set_version(conn, to_ver)

                # Log success
                log_migration(conn, from_ver, to_ver, success=True)

                # Commit transaction
                conn.commit()

                print(f"   ✅ Migration {from_ver} -> {to_ver} completed")

            except Exception as e:
                # Rollback on error
                conn.rollback()

                error_msg = str(e)
                print(f"   ❌ Migration {from_ver} -> {to_ver} failed: {error_msg}")

                # Log failure
                log_migration(conn, from_ver, to_ver, success=False, error_message=error_msg)

                return False

        print(f"\n✅ All migrations completed successfully")
        print(f"   Final version: {get_current_version(conn)}")
        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        conn.close()


def get_migration_history(db_path: Optional[str] = None) -> list:
    """
    Get migration history from database

    Args:
        db_path: Path to database file

    Returns:
        List of migration records
    """
    if db_path is None:
        db_path = DEFAULT_DATABASE_FILE

    if not Path(db_path).exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Check if migration_log table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='migration_log'"
        )
        if not cursor.fetchone():
            return []

        cursor = conn.execute(
            """
            SELECT from_version, to_version, applied_at, success, error_message
            FROM migration_log
            ORDER BY applied_at DESC
            """
        )

        return [dict(row) for row in cursor.fetchall()]

    finally:
        conn.close()


# ============================================================================
# Migration Definitions
# ============================================================================
# Future migrations will be added here as new versions are released

# Example migration (commented out - no v2 yet):
# @migration(from_version=1, to_version=2)
# def add_rating_field(conn: sqlite3.Connection):
#     """Add rating field to movies table"""
#     conn.execute("ALTER TABLE movies ADD COLUMN rating REAL")
#     conn.execute("CREATE INDEX idx_movies_rating ON movies(rating)")


def main():
    """Command-line interface for migration management"""
    import argparse

    parser = argparse.ArgumentParser(description="HackFlix Database Migration Tool")
    parser.add_argument("--db", default=DEFAULT_DATABASE_FILE, help="Database file path")
    parser.add_argument("--migrate", action="store_true", help="Run migrations")
    parser.add_argument("--target", type=int, help="Target version (default: latest)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--history", action="store_true", help="Show migration history")
    parser.add_argument("--version", action="store_true", help="Show current version")

    args = parser.parse_args()

    if args.version:
        conn = sqlite3.connect(args.db)
        try:
            current = get_current_version(conn)
            print(f"Current version: {current}")
            print(f"Latest version: {DATABASE_VERSION}")
        finally:
            conn.close()

    elif args.history:
        history = get_migration_history(args.db)
        if not history:
            print("No migration history found")
        else:
            print(f"Migration History ({len(history)} entries):\n")
            for entry in history:
                status = "✅" if entry["success"] else "❌"
                print(f"{status} {entry['from_version']} -> {entry['to_version']}")
                print(f"   Applied: {entry['applied_at']}")
                if entry["error_message"]:
                    print(f"   Error: {entry['error_message']}")
                print()

    elif args.migrate:
        migrate_database(args.db, args.target, args.dry_run)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
