#!/bin/sh
# entrypoint for container: upgrade db then start application

# apply any pending migrations; ignore errors if DB not initialized yet
python -m alembic upgrade head

# execute the command given as CMD/arguments
exec "$@"
