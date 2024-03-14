#!/bin/bash

# Enter the virtual environment
source venv/bin/activate

echo "Running migrations..."

# Set the DATABASE_URL environment variable
source .env

# If the DATABASE_URL environment variable is not set, set a default value
if [ -z "$DATABASE_URL" ]; then
  export DATABASE_URL=sqlite:///./data/app.db
fi

echo "DATABASE_URL: $DATABASE_URL"

# Run the migrations
alembic upgrade head

# Deactivate the virtual environment
deactivate

# Exit the script
exit 0