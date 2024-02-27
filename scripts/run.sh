
#!/bin/bash

source venv/bin/activate

export DEBUG=false
python3 src/app.py > /dev/null 2>&1

# Deactivate the virtual environment
deactivate

# Exit the script
exit 0