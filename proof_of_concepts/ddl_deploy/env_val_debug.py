from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Print loaded variables
print("Loaded environment variables:")
print("SNOWFLAKE_USER:", os.getenv('SNOWFLAKE_USER'))
print("SNOWFLAKE_PASSWORD:", os.getenv('SNOWFLAKE_PASSWORD'))
print("SNOWFLAKE_ACCOUNT:", os.getenv('SNOWFLAKE_ACCOUNT'))
print("SNOWFLAKE_WAREHOUSE:", os.getenv('SNOWFLAKE_WAREHOUSE'))
print("SNOWFLAKE_DATABASE:", os.getenv('SNOWFLAKE_DATABASE'))
print("SNOWFLAKE_SCHEMA:", os.getenv('SNOWFLAKE_SCHEMA'))
