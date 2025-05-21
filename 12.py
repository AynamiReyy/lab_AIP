import json


def display_products_from_json(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            data = json.load(file)

            for product in data['products']:
                print(f"Название: {product['name']}")
                print(f"Цена: {product['price']}")
                print(f"Вес: {product['weight']}")

                if product['available']:
                    print("В наличии\n")
                else:
                    print("Нет в наличии!\n")

    except FileNotFoundError:
        print(f"Файл {filename} не найден.")
    except json.JSONDecodeError:
        print("Ошибка чтения JSON файла.")
    except KeyError:
        print("Некорректная структура JSON файла.")
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")


filename = 'products.json'
display_products_from_json(filename)