import os
import sys
import hashlib
import time
import logging
import snowflake.connector
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    # Load environment variables
    load_dotenv()

    # Retrieve Snowflake credentials
    snowflake_user = os.getenv('SNOWFLAKE_USER')
    snowflake_password = os.getenv('SNOWFLAKE_PASSWORD')
    snowflake_account = os.getenv('SNOWFLAKE_ACCOUNT')
    snowflake_warehouse = os.getenv('SNOWFLAKE_WAREHOUSE')
    snowflake_schema = os.getenv('SNOWFLAKE_SCHEMA')
    snowflake_role = os.getenv('SNOWFLAKE_ROLE')

    # Get branch name from GitLab CI environment
    target_branch = os.getenv('CI_COMMIT_BRANCH')
    if not target_branch:
        raise EnvironmentError("CI_COMMIT_BRANCH is not set. Are you running inside a GitLab CI pipeline?")

    # Map branch to Snowflake database
    branch_to_db = {
        'dev': 'pdil_dev_s4',
        'test': 'pdil_sat_03',
        'main': 'pdil_prod'
    }

    snowflake_database = branch_to_db.get(target_branch)
    if not snowflake_database:
        raise ValueError(f"Unsupported branch '{target_branch}' for database mapping.")

    # Log the selected database for audit
    logging.info(f"'{snowflake_database}' Snowflake database is used for '{target_branch}' branch")

    # Validate credentials
    required_vars = {
        'SNOWFLAKE_USER': snowflake_user,
        'SNOWFLAKE_PASSWORD': snowflake_password,
        'SNOWFLAKE_ACCOUNT': snowflake_account,
        'SNOWFLAKE_WAREHOUSE': snowflake_warehouse,
        'SNOWFLAKE_DATABASE': snowflake_database,
        'SNOWFLAKE_SCHEMA': snowflake_schema,
        'SNOWFLAKE_ROLE': snowflake_role
    }
    missing_vars = [k for k, v in required_vars.items() if not v]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    # Connect to Snowflake
    conn = snowflake.connector.connect(
        user=snowflake_user,
        password=snowflake_password,
        account=snowflake_account,
        warehouse=snowflake_warehouse,
        database=snowflake_database,
        schema=snowflake_schema,
        role=snowflake_role,
        login_timeout=30,
        client_session_keep_alive=False
    )
    cursor = conn.cursor()

    # Ensure tracking table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS itr_fmshub_cleanse.ddl_execution_log (
            schema_name VARCHAR(100),
            file_name VARCHAR(1000),
            object_type VARCHAR(100),
            modified_time FLOAT,
            checksum STRING,
            executed_at TIMESTAMP_TZ,
            PRIMARY KEY (schema_name, file_name)
        )
    """)

    # Load previously executed checksums
    cursor.execute("SELECT checksum FROM itr_fmshub_cleanse.ddl_execution_log")
    executed_checksums = set(row[0] for row in cursor.fetchall())

    # Folder execution order
    ddl_dir = 'sql_scripts'
    ordered_folders = ['table', 'sequence', 'view', 'udf', 'procedure']
    folder_ddls = {folder: [] for folder in ordered_folders}

    def compute_checksum(filepath):
        with open(filepath, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    # Collect new DDLs grouped by folder
    for root, _, files in os.walk(ddl_dir):
        for filename in files:
            if filename.endswith('.sql'):
                filepath = os.path.join(root, filename)
                checksum = compute_checksum(filepath)
                if checksum in executed_checksums:
                    continue

                relative_path = os.path.relpath(filepath, ddl_dir)
                file_name = os.path.basename(relative_path)
                parts = relative_path.split(os.sep)
                schema_name = parts[0] if len(parts) > 1 else 'UNKNOWN'
                object_type = parts[-2] if len(parts) > 2 else 'UNKNOWN'

                for folder in ordered_folders:
                    if folder in parts:
                        modified_time = os.path.getmtime(filepath)
                        folder_ddls[folder].append((filepath, file_name, modified_time, checksum, schema_name, object_type))
                        break

    # Execute DDLs folder by folder
    executed_any_ddls = False
    for folder in ordered_folders:
        ddls = sorted(folder_ddls[folder], key=lambda x: x[1])  # Sort by filename
        for filepath, file_name, modified_time, checksum, schema_name, object_type in ddls:
            with open(filepath, 'r') as f:
                ddl = f.read()
                logging.info(f"Executing {folder}/{file_name}...")
                start_time = time.time()
                try:
                    cursor.execute(ddl)
                    duration = time.time() - start_time
                    logging.info(f"Executed {file_name} in {duration:.2f} seconds")

                    # Log execution
                    cursor.execute("""
                        MERGE INTO itr_fmshub_cleanse.ddl_execution_log t
                        USING (SELECT %s AS file_name, %s AS modified_time, %s AS checksum,
                                      CURRENT_TIMESTAMP AS executed_at, %s AS schema_name, %s AS object_type) s
                        ON t.schema_name = s.schema_name AND t.file_name = s.file_name
                        WHEN MATCHED THEN UPDATE SET
                            t.modified_time = s.modified_time,
                            t.checksum = s.checksum,
                            t.executed_at = s.executed_at,
                            t.object_type = s.object_type
                        WHEN NOT MATCHED THEN INSERT (
                            file_name, modified_time, checksum, executed_at, schema_name, object_type
                        )
                        VALUES (
                            s.file_name, s.modified_time, s.checksum, s.executed_at, s.schema_name, s.object_type
                        )
                    """, (file_name, modified_time, checksum, schema_name, object_type))

                    executed_any_ddls = True
                except Exception as e:
                    logging.error(f"Failed to execute {file_name}: {e}")
                    sys.exit(1)

    cursor.close()
    conn.close()

    # Final message
    if executed_any_ddls:
        logging.info("All new or modified DDLs executed successfully.")
    else:
        logging.info("No new DDLs to execute.")

except Exception as e:
    logging.error(f"Unhandled error: {e}")
    sys.exit(1)