from PIL import Image
import os


def display_image_info(file_path):
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in ('.jpg', '.jpeg', '.png'):
            print(f"Файл {file_path} не является изображением JPG или PNG.")
            return

        with Image.open(file_path) as img:
            img.show()

            width, height = img.size
            img_format = img.format
            img_mode = img.mode

            print(f"Информация об изображении {file_path}:")
            print(f"Размер: {width}x{height} пикселей")
            print(f"Формат: {img_format}")
            print(f"Цветовая модель: {img_mode}")

    except FileNotFoundError:
        print(f"Файл {file_path} не найден.")
    except Exception as e:
        print(f"Произошла ошибка при обработке файла {file_path}: {str(e)}")


file_path = input("Введите путь к файлу изображения (JPG/PNG): ")
display_image_info(file_path)