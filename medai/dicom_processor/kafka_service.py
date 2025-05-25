from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def send_to_kafka(topic, message):
    try:
        producer.send(topic, message)
        producer.flush()
        print(f"✅ Успешно отправлено в {topic}: {message}")
    except Exception as e:
        print(f"❌ Ошибка отправки в Kafka: {str(e)}")