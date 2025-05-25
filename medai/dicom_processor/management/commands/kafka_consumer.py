import json
import logging
import os
import signal
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from dicom_processor.models import DicomStudy
from dicom_processor.services.model_service import HipFractureDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Kafka Consumer for processing DICOM studies'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = False
        self.consumer = None
        self.producer = None
        self.detector = None

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-retries',
            type=int,
            default=3,
            help='Max retries for processing a message'
        )

    def setup_detector(self):
        """Initialize the fracture detection model"""
        try:
            model_path = 'models/hip_fracture_model_resnet18.pth'
            self.detector = HipFractureDetector(model_path)
            logger.info(f"Successfully loaded model from {model_path}")
        except Exception as e:
            logger.error(f"Failed to initialize detector: {str(e)}", exc_info=True)
            raise

    def setup_kafka(self):
        """Initialize Kafka connections"""
        try:
            self.consumer = KafkaConsumer(
                'dicom_studies',
                bootstrap_servers=['localhost:9092'],
                value_deserializer=self.safe_deserializer,
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                consumer_timeout_ms=1000,
                group_id='dicom_processor_group'
            )

            self.producer = KafkaProducer(
                bootstrap_servers=['localhost:9092'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )

            logger.info("Kafka connections established")
        except KafkaError as e:
            logger.error(f"Kafka connection error: {str(e)}", exc_info=True)
            raise

    def safe_deserializer(self, message):
        """Safe message deserializer that handles invalid JSON"""
        if not message:
            return None

        try:
            return json.loads(message.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {message[:100] if message else 'None'}")
            return None
        except Exception as e:
            logger.error(f"Unexpected deserialization error: {str(e)}")
            return None

    def handle(self, *args, **options):
        self.running = True

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        try:
            self.setup_detector()
            self.setup_kafka()

            logger.info("Starting DICOM processing consumer...")
            self.run_consumer(options['max_retries'])

        except Exception as e:
            logger.critical(f"Fatal error: {str(e)}", exc_info=True)
            raise
        finally:
            self.cleanup()

    def run_consumer(self, max_retries):
        """Main consumer loop"""
        retry_count = 0

        while self.running:
            try:
                records = self.consumer.poll(timeout_ms=1000)

                if not records:
                    if not self.running:
                        break
                    continue

                # Reset retry count on successful poll
                retry_count = 0

                for _, messages in records.items():
                    for message in messages:
                        if not self.running:
                            break

                        if not message.value:
                            logger.warning("Received empty message value")
                            continue

                        self.process_message(message)

            except KafkaError as e:
                retry_count += 1
                logger.error(f"Kafka error (attempt {retry_count}/{max_retries}): {str(e)}")

                if retry_count >= max_retries:
                    logger.error("Max retries exceeded. Shutting down...")
                    self.running = False
                else:
                    time.sleep(min(2 ** retry_count, 10))  # Exponential backoff

            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}", exc_info=True)
                continue

    def process_message(self, message):
        """Process a single DICOM study message"""
        try:
            # Message already deserialized by safe_deserializer
            message_data = message.value

            if not message_data:
                logger.warning("Empty message data after deserialization")
                return

            # Extract study ID
            study_id = message_data.get('study_id')
            if not study_id:
                logger.error("Missing study_id in message")
                return

            logger.info(f"Processing study {study_id}")

            # Process in transaction
            with transaction.atomic():
                study = self.get_study_for_processing(study_id)
                if not study:
                    return

                try:
                    # Process DICOM file
                    result = self.process_dicom_file(study)

                    # Update study with results
                    self.update_study_results(study, result)
                    logger.info(f"Study {study_id} processed successfully")

                except Exception as e:
                    logger.error(f"Processing failed for study {study_id}: {str(e)}", exc_info=True)
                    self.handle_processing_failure(study)
                    raise

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)

    # ... (остальные методы остаются без изменений, как в предыдущем примере) ...

    def shutdown(self, signum, frame):
        """Graceful shutdown handler"""
        if self.running:
            logger.info("Shutdown signal received. Initiating graceful shutdown...")
            self.running = False
        else:
            logger.warning("Forced shutdown initiated")
            self.cleanup()
            raise SystemExit(1)

    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up resources...")

        try:
            if self.consumer:
                self.consumer.close()
                logger.info("Kafka consumer closed")
        except Exception as e:
            logger.error(f"Error closing consumer: {str(e)}")

        try:
            if self.producer:
                self.producer.close()
                logger.info("Kafka producer closed")
        except Exception as e:
            logger.error(f"Error closing producer: {str(e)}")

        logger.info("Shutdown complete")

    def get_study_for_processing(self, study_id):
        """Lock and retrieve study for processing"""
        try:
            study = DicomStudy.objects.select_for_update().get(id=study_id)
            study.processing_status = 'processing'
            study.save(update_fields=['processing_status'])
            return study
        except DicomStudy.DoesNotExist:
            logger.error(f"Study {study_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error retrieving study {study_id}: {str(e)}")
            return None

    def process_dicom_file(self, study):
        """Process DICOM file and return results"""
        if not study.dicom_file:
            raise ValueError("DICOM file not attached")

        dicom_path = study.dicom_file.path
        if not os.path.exists(dicom_path):
            raise FileNotFoundError(f"DICOM file missing at {dicom_path}")

        return self.detector.process_dicom(dicom_path)

    def update_study_results(self, study, results):
        """Update study with processing results"""
        left_pred, right_pred = results
        study.result_left_hip = left_pred
        study.result_right_hip = right_pred
        study.processing_status = 'completed'
        study.save(update_fields=[
            'result_left_hip',
            'result_right_hip',
            'processing_status'
        ])

    def handle_processing_failure(self, study):
        """Handle processing failures"""
        study.processing_status = 'failed'
        study.save(update_fields=['processing_status'])
        self.send_processing_notification(study.id, 'failed')

    def send_processing_notification(self, study_id, status):
        """Send processing status notification"""
        try:
            message = {
                'study_id': study_id,
                'status': status,
                'timestamp': int(time.time())
            }
            self.producer.send('dicom_processing_status', message)
            self.producer.flush()
        except Exception as e:
            logger.error(f"Failed to send status notification: {str(e)}")