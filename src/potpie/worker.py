import os
from celery import Celery

# Get configuration from environment variables
mongodb_uri = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/celery_results')
rabbitmq_uri = os.environ.get('RABBITMQ_URI', 'amqp://guest:guest@localhost:5672//')

# Create Celery instance
app = Celery(
    'worker',
    broker=rabbitmq_uri,
    backend=mongodb_uri
)

# Configure Celery
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True
)

# Define a simple task
@app.task
def process_task(x, y):
    """Task to add two numbers."""
    return x + y

if __name__ == '__main__':
    app.worker_main()