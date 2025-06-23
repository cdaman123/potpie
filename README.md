# Potpie Project

## Project Overview

This project is a web application built with FastAPI and a Celery worker for background tasks. It uses MongoDB as a database and RabbitMQ as a message broker for Celery.

## Setup

1.  **Install Poetry (if not already installed):**
    If you don't have Poetry installed, follow the official documentation: [https://python-poetry.org/docs/#installation](https://python-poetry.org/docs/#installation)

2.  **Install dependencies:** (ensure python version should be `>=3.12`)

    `poetry install`

3.  **Configure environment variables:**
    Copy the `.env.example` file to `.env` and update the values as needed.


    Copy the `.env.sample` file to `.env`:

    `cp .env.sample .env`

    Edit the `.env` file with your specific configurations.

4.  **Start RabbitMQ and MongoDB:**

    Use the command `docker compose up -d rabbitmq mongodb` to start the services.

5.  **Start FastAPI and Celery:**

    *   **Using Docker Compose:**
        Use the command `docker compose up -d fastapi celery` to start the FastAPI application and Celery worker as Docker containers.

    *   **Using Command Line:**
        Alternatively, you can start the FastAPI application and Celery worker directly from your terminal:
        *   For FastAPI: `poetry run uvicorn src.potpie.main:app --reload`
        *   For Celery: `poetry run celery -A src.potpie.worker worker -l info`
