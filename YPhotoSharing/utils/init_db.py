"""
Database initialisation utility for YPhotoSharing.

Creates all schema tables for the configured database backend
(SQLite, PostgreSQL, or MySQL).
"""

import argparse
import logging
import sys
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine, inspect

from YPhotoSharing.YServer.classes.models import Base


def create_engine_from_config(db_config: dict, config_path: Path = None):
    """Build a SQLAlchemy engine from a database config dict."""
    db_type = db_config.get("type", "sqlite")

    if db_type == "sqlite":
        sqlite_cfg = db_config.get("sqlite", {})
        filename = sqlite_cfg.get("filename", "yphotosharing.db")
        db_path = (Path(config_path) / filename) if config_path else Path(filename)
        return create_engine(f"sqlite:///{db_path}", echo=False)

    elif db_type == "postgresql":
        pg = db_config.get("postgresql", {})
        pwd = quote_plus(pg.get("password", "")) if pg.get("password") else ""
        auth = f"{pg.get('username','postgres')}:{pwd}@" if pwd else f"{pg.get('username','postgres')}@"
        url = (
            f"postgresql+psycopg2://{auth}"
            f"{pg.get('host','localhost')}:{pg.get('port',5432)}"
            f"/{pg.get('database','yphotosharing')}"
        )
        return create_engine(url, echo=False)

    elif db_type == "mysql":
        my = db_config.get("mysql", {})
        pwd = quote_plus(my.get("password", "")) if my.get("password") else ""
        auth = f"{my.get('username','root')}:{pwd}@" if pwd else f"{my.get('username','root')}@"
        url = (
            f"mysql+pymysql://{auth}"
            f"{my.get('host','localhost')}:{my.get('port',3306)}"
            f"/{my.get('database','yphotosharing')}"
        )
        return create_engine(url, echo=False)

    raise ValueError(f"Unsupported database type: {db_type}")


def initialize_database(db_config: dict, config_path: Path = None,
                        logger: logging.Logger = None) -> bool:
    """Create all tables. Returns True on success."""
    try:
        engine = create_engine_from_config(db_config, config_path)
        Base.metadata.create_all(engine)
        msg = f"Database initialised ({db_config.get('type','sqlite')})"
        if logger:
            logger.info(msg)
        else:
            print(f"✅ {msg}")
        return True
    except Exception as exc:
        msg = f"Failed to initialise database: {exc}"
        if logger:
            logger.error(msg)
        else:
            print(f"❌ {msg}")
        return False


def database_exists(db_config: dict, config_path: Path = None) -> bool:
    """Check whether the database (or its tables) already exists."""
    db_type = db_config.get("type", "sqlite")
    if db_type == "sqlite":
        filename = db_config.get("sqlite", {}).get("filename", "yphotosharing.db")
        db_path = (Path(config_path) / filename) if config_path else Path(filename)
        return db_path.exists()
    try:
        engine = create_engine_from_config(db_config, config_path)
        return len(inspect(engine).get_table_names()) > 0
    except Exception:
        return False


# ------------------------------------------------------------------ CLI

def main():
    parser = argparse.ArgumentParser(
        description="Initialise the YPhotoSharing database schema"
    )
    parser.add_argument("--db-type", choices=["sqlite", "postgresql", "mysql"],
                        default="sqlite")
    parser.add_argument("--config-path", type=str)
    parser.add_argument("--sqlite-filename", default="yphotosharing.db")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="yphotosharing")
    parser.add_argument("--pg-user", default="postgres")
    parser.add_argument("--pg-password", default="")
    parser.add_argument("--mysql-host", default="localhost")
    parser.add_argument("--mysql-port", type=int, default=3306)
    parser.add_argument("--mysql-database", default="yphotosharing")
    parser.add_argument("--mysql-user", default="root")
    parser.add_argument("--mysql-password", default="")
    args = parser.parse_args()

    db_config: dict = {"type": args.db_type}
    if args.db_type == "sqlite":
        db_config["sqlite"] = {"filename": args.sqlite_filename}
    elif args.db_type == "postgresql":
        db_config["postgresql"] = {
            "host": args.pg_host, "port": args.pg_port,
            "database": args.pg_database,
            "username": args.pg_user, "password": args.pg_password,
        }
    elif args.db_type == "mysql":
        db_config["mysql"] = {
            "host": args.mysql_host, "port": args.mysql_port,
            "database": args.mysql_database,
            "username": args.mysql_user, "password": args.mysql_password,
        }

    config_path = Path(args.config_path) if args.config_path else None
    success = initialize_database(db_config, config_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
