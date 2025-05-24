from kafka import KafkaProducer, KafkaConsumer
import json

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def send_to_kafka(topic, message):
    producer.send(topic, message)
    producer.flush()

# Потребитель (Consumer) будем настраивать позже