
#!/bin/bash

source venv/bin/activate

source .env
export DATABASE_URL=sqlite:///./data/app.db
export LOG_PATH=./data/app.log
export DEBUG=False
python3 src/app.py

# Deactivate the virtual environment
deactivate

# Exit the script
exit 0
