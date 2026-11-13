"""The server configuration of a new photo-sharing experiment."""


def generate_photo_sharing_config(
    exp_name,
    db_type,
    db_uri,
    topics,
    data_path,
    db_config_dict=None,
    is_remote=False,
):
    """Generate config file for the YPhotoSharing simulator type."""
    database_config = {
        "type": db_type,
    }

    if db_type == "sqlite":
        database_config["sqlite"] = {"filename": "yphotosharing.db"}
    elif db_type == "postgresql":
        if db_config_dict:
            database_config["postgresql"] = db_config_dict
        else:
            database_config["postgresql"] = {
                "host": "localhost",
                "port": 5432,
                "database": "yphotosharing",
                "username": "postgres",
                "password": "password",
            }

    config = {
        "server_name": "orchestrator_server",
        "namespace": "yphotosharing",
        "min_to_start": 1,
        "timeout_seconds": 60,
        "database": database_config,
        "simulation": {
            "num_rounds": 48,
            "discussion_topics": [t.strip() for t in topics if t.strip()],
        },
        "logging": {
            "enable_server_log": True,
            "enable_console_log": True,
        },
        "platform_type": "photo_sharing",
        "database_uri": db_uri,
        "data_path": data_path,
        "is_remote": is_remote,
        "experiment_name": exp_name,
    }

    return config
