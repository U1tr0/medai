from kafka import KafkaProducer
import json
import logging

# Настройка логгера
logger = logging.getLogger(__name__)
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)


def send_to_kafka(topic, message):
    try:
        if not isinstance(message, dict):
            raise ValueError("Message must be a dictionary")

        producer.send(topic, message)
        producer.flush()
        logger.info(f"✅ Successfully sent to {topic}: {message}")
    except Exception as e:
        logger.error(f"❌ Failed to send to Kafka: {str(e)}")