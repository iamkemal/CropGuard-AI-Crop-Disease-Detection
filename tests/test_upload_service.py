import tempfile
import unittest
from contextlib import closing
from io import BytesIO
from pathlib import Path

from PIL import Image
from werkzeug.datastructures import FileStorage

from app.services.upload_service import UploadValidationError, save_crop_image


class CropImageUploadTests(unittest.TestCase):
    def create_image_upload(
        self,
        image_format: str = "PNG",
        filename: str = "plant.png",
    ) -> FileStorage:
        image_data = BytesIO()
        Image.new("RGB", (40, 30), color=(30, 120, 55)).save(
            image_data,
            format=image_format,
        )
        image_data.seek(0)
        return FileStorage(stream=image_data, filename=filename)

    def test_saves_valid_image_using_generated_name_and_reencodes_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            saved_name = save_crop_image(
                self.create_image_upload(),
                temporary_directory,
            )
            saved_path = Path(temporary_directory) / saved_name

            self.assertRegex(saved_name, r"^[0-9a-f]{32}\.png$")
            with Image.open(saved_path) as saved_image:
                self.assertEqual(saved_image.format, "PNG")
                self.assertEqual(saved_image.size, (40, 30))

    def test_accepts_each_supported_raster_format(self) -> None:
        image_variants = (
            ("JPEG", "field.jpg"),
            ("JPEG", "field.jpeg"),
            ("PNG", "field.png"),
            ("WEBP", "field.webp"),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            for image_format, filename in image_variants:
                with self.subTest(filename=filename):
                    saved_name = save_crop_image(
                        self.create_image_upload(image_format, filename),
                        temporary_directory,
                    )
                    with Image.open(Path(temporary_directory) / saved_name) as image:
                        self.assertEqual(image.format, image_format)

    def test_rejects_unsupported_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(UploadValidationError, "JPG, JPEG, PNG, or WEBP"):
                save_crop_image(
                    self.create_image_upload(filename="plant.svg"),
                    temporary_directory,
                )

    def test_rejects_content_that_does_not_match_its_extension(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(UploadValidationError, "does not match"):
                save_crop_image(
                    self.create_image_upload("PNG", "plant.jpg"),
                    temporary_directory,
                )

    def test_rejects_corrupt_image_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            corrupt_upload = FileStorage(
                stream=BytesIO(b"not an image"),
                filename="plant.png",
            )
            with self.assertRaisesRegex(UploadValidationError, "not a valid"):
                save_crop_image(corrupt_upload, temporary_directory)
            self.assertEqual(list(Path(temporary_directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
