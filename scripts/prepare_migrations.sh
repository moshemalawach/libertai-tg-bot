#!/bin/bash

# Enter the virtual environment
source venv/bin/activate

# Generate alembic migrations
echo "Generating migrations..."

# Set the DATABASE_URL environment variable
source .env

# If the DATABASE_URL environment variable is not set, set a default value
if [ -z "$DATABASE_URL" ]; then
  export DATABASE_URL=sqlite:///./data/app.db
fi

echo "DATABASE_URL: $DATABASE_URL"

# Generate alembic migrations
# Get the current datetime
now=$(date +"%Y_%m_%d_%H_%M_%S")
alembic revision --autogenerate -m "migration_$now"

# Deactivate the virtual environment
deactivate

# Exit the script
exit 0
