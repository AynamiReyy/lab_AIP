from pathlib import Path
from PIL import Image

holiday_images = {
    "8 МАРТА": "картинки/8 марта.jpg",
    "1 МАЙ": "картинки/1 май.jpg",
    "НОВЫЙ ГОД": "картинки/новый год.jpg",
    "ДЕНЬ РОЖДЕНИЯ": "картинки/открытка.jpg"
}

user_input = input("Введите название праздника: ").upper()

if user_input in holiday_images:
    image_path = Path(holiday_images[user_input])

    if image_path.exists():
        try:
            with Image.open(image_path) as img:
                img.show()
        except Exception as e:
            print(f"Не удалось открыть изображение: {e}")
    else:
        print(f"Изображение не найдено по пути: {image_path}")
else:
    print("Такой праздник не найден в базе. Доступные варианты:")
    for holiday in holiday_images.keys():
        print(f"- {holiday}")