# Use the official lightweight Python image.
FROM python:3.11-slim

# Set the working directory in the container.
WORKDIR /app

# Copy only the necessary files to install the package.
COPY setup.py /app/
COPY air_download /app/air_download/

# Install the Python package along with dependencies.
RUN pip install --no-cache-dir .

# Define the default command to run the package.
ENTRYPOINT ["air_download"]
