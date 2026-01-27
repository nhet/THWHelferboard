# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the backend directory into the container at /app.
COPY ./backend/ /app/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install nano
RUN apt-get update && apt-get install -y nano && rm -rf /var/lib/apt/lists/*

# Define mount points for the database and uploads.
# These directories can be mounted as volumes from the host or a named volume
# when running the container.
# Example: docker run -p 8080:80 -v my-db-volume:/app/db -v my-uploads-volume:/app/app/static/uploads <image-name>
VOLUME /app/db
VOLUME /app/app/static/uploads

# Expose port 80 for the application
EXPOSE 80

# The command to run the Uvicorn server for the FastAPI application.
# It will listen on all interfaces on port 80.
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "80"]
