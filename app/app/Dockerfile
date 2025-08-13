# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
# Prevents Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE 1
# Ensures Python output is sent straight to the terminal without buffering
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Make port 8080 available to the world outside this container
# Cloud Run expects the container to listen on the port defined by the PORT env var (default 8080)
EXPOSE 8080

# Define the command to run your app using uvicorn
# Use the PORT environment variable provided by Cloud Run
CMD ["uvicorn", "manychat_webhook_fixed:app", "--host", "0.0.0.0", "--port", "8080"] 