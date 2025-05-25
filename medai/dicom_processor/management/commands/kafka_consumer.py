from django.core.management.base import BaseCommand
from kafka import KafkaConsumer
import json
from dicom_processor.models import DicomStudy
from django.db import transaction
import logging
from model_service import HipFractureDetector

# Настройка логирования
logger = logging.getLogger(__name__)
MODEL_PATH = 'hip_fracture_model_resnet18.pth'
detector = HipFractureDetector(MODEL_PATH)

class Command(BaseCommand):
    help = 'Kafka Consumer for DICOM studies processing'

    def handle(self, *args, **options):
        # Инициализация Kafka Consumer
        consumer = KafkaConsumer(
            'dicom_studies',
            bootstrap_servers=['localhost:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True
        )

        logger.info("Kafka Consumer started and connected to topic 'dicom_studies'")

        for message in consumer:
            try:
                message_value = message.value
                logger.info(f"Received message: {message_value}")

                study_id = message_value['study_id']

                # Блокируем запись для обработки
                with transaction.atomic():
                    study = DicomStudy.objects.select_for_update().get(id=study_id)
                    logger.info(f"Processing study ID: {study.id}, current status: {study.processing_status}")

                    # Обновляем статус
                    study.processing_status = 'processing'
                    study.save()
                    logger.info(f"Status updated to 'processing' for study {study.id}")

                    # Здесь будет вызов ML-модели (заглушка)
                    study.result_left_hip = False
                    study.result_right_hip = True

                    # Финализируем обработку
                    study.processing_status = 'completed'
                    study.save()
                    logger.info(f"Successfully processed study {study.id}. Final status: {study.processing_status}")

            except DicomStudy.DoesNotExist:
                logger.error(f"Study with ID {study_id} not found in database")
            except Exception as e:
                logger.error(f"Error processing study {study_id}: {str(e)}", exc_info=True)
                # Можно добавить повторную попытку или dead letter queue


if __name__ == '__main__':
    Command().handle()