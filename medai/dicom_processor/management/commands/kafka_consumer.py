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
from django.conf import settings

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
        parser.add_argument(
            '--model-path',
            type=str,
            default='models/hip_fracture_model_resnet18.pth',
            help='Path to trained model file'
        )

    def setup_detector(self, model_path):
        """Initialize the fracture detection model"""
        try:
            self.detector = HipFractureDetector(model_path)
            logger.info(f"Successfully loaded model from {model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize detector: {str(e)}", exc_info=True)
            return False

    def setup_kafka(self):
        """Initialize Kafka connections"""
        try:
            self.consumer = KafkaConsumer(
                'dicom_studies',
                bootstrap_servers=['localhost:9092'],
                value_deserializer=lambda v: json.loads(v.decode('utf-8')) if v else None,
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
            return True
        except KafkaError as e:
            logger.error(f"Kafka connection error: {str(e)}", exc_info=True)
            return False

    def handle(self, *args, **options):
        self.running = True

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        # Initialize components
        if not self.setup_detector(options['model_path']):
            return
        if not self.setup_kafka():
            return

        logger.info("Starting DICOM processing consumer...")
        self.run_consumer(options['max_retries'])

    def run_consumer(self, max_retries):
        """Main consumer loop"""
        retry_count = 0

        while self.running:
            try:
                # Poll for messages
                batch = self.consumer.poll(timeout_ms=1000)
                if not batch:
                    if not self.running:
                        break
                    continue

                # Reset retry count on successful poll
                retry_count = 0

                # Process each message in the batch
                for _, messages in batch.items():
                    for message in messages:
                        if not self.running:
                            break

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
            study_id = message.value.get('study_id')
            if not study_id:
                logger.error("Missing study_id in message")
                return

            logger.info(f"Processing study {study_id}")

            with transaction.atomic():
                study = DicomStudy.objects.select_for_update().get(id=study_id)

                # Update status to processing
                study.processing_status = 'processing'
                study.save(update_fields=['processing_status'])

                try:
                    # Process the DICOM file
                    result = self.process_dicom_file(study)

                    # Update study with results
                    self.update_study_results(study, result)
                    logger.info(f"Successfully processed study {study_id}")

                except Exception as e:
                    logger.error(f"Failed to process study {study_id}: {str(e)}", exc_info=True)
                    study.processing_status = 'failed'
                    study.save(update_fields=['processing_status'])
                    raise

        except DicomStudy.DoesNotExist:
            logger.error(f"Study {study_id} not found")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)

    def process_dicom_file(self, study):
        """Process DICOM file and return results"""
        try:
            dicom_path = study.dicom_file.path
            logger.info(f"Processing DICOM file: {dicom_path}")

            # Process with detector
            result = self.detector.process_dicom(dicom_path)

            if result['status'] == 'failed':
                raise Exception(result.get('error', 'Unknown error during processing'))

            # Save preview and split images
            self.save_dicom_images(study, dicom_path)

            return result

        except Exception as e:
            logger.error(f"DICOM processing failed: {str(e)}", exc_info=True)
            raise

    def save_dicom_images(self, study, dicom_path):
        """Save DICOM preview and split images"""
        try:
            import pydicom
            from PIL import Image
            import numpy as np

            # Create directories if not exist
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'dicom_previews'), exist_ok=True)
            os.makedirs(os.path.join(settings.MEDIA_ROOT, 'processed'), exist_ok=True)

            # Read DICOM and convert to image
            ds = pydicom.dcmread(dicom_path)
            pixel_array = ds.pixel_array
            pixel_array = (pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min()) * 255
            pixel_array = pixel_array.astype(np.uint8)
            img = Image.fromarray(pixel_array)

            # Save preview
            preview_path = os.path.join('dicom_previews', f'preview_{study.id}.jpg')
            img.save(os.path.join(settings.MEDIA_ROOT, preview_path))
            study.dicom_preview = preview_path

            # Save split images
            width, height = img.size
            left_img = img.crop((0, 0, width // 2, height))
            right_img = img.crop((width // 2, 0, width, height))

            left_path = os.path.join('processed', f'left_{study.id}.jpg')
            right_path = os.path.join('processed', f'right_{study.id}.jpg')

            left_img.save(os.path.join(settings.MEDIA_ROOT, left_path))
            right_img.save(os.path.join(settings.MEDIA_ROOT, right_path))

            study.left_hip_image = left_path
            study.right_hip_image = right_path

        except Exception as e:
            logger.error(f"Failed to save DICOM images: {str(e)}")
            raise

    def update_study_results(self, study, result):
        """Update study with processing results"""
        study.result_left_hip = result['left_pred']
        study.result_right_hip = result['right_pred']
        study.confidence_left = result['left_confidence']
        study.confidence_right = result['right_confidence']
        study.processing_status = 'completed'
        study.save(update_fields=[
            'result_left_hip',
            'result_right_hip',
            'confidence_left',
            'confidence_right',
            'processing_status',
            'dicom_preview',
            'left_hip_image',
            'right_hip_image'
        ])

    def shutdown(self, signum, frame):
        """Graceful shutdown handler"""
        logger.info("Shutdown signal received. Initiating graceful shutdown...")
        self.running = False

    def cleanup(self):
        """Clean up resources"""
        try:
            if self.consumer:
                self.consumer.close()
            if self.producer:
                self.producer.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
        finally:
            logger.info("Consumer shutdown complete")