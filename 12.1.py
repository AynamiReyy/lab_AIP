import json


def load_products(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        return {"products": []}
    except json.JSONDecodeError:
        print("Ошибка чтения файла. Создана новая структура данных.")
        return {"products": []}


def save_products(filename, data):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def add_product(data):
    print("\nДобавление нового продукта:")
    name = input("Название: ")
    price = int(input("Цена: "))
    available = input("В наличии (да/нет): ").lower() == 'да'
    weight = int(input("Вес: "))

    new_product = {
        "name": name,
        "price": price,
        "available": available,
        "weight": weight
    }

    data['products'].append(new_product)
    print("Продукт успешно добавлен!")


def display_products(data):
    print("\nТекущий список продуктов:")
    for product in data['products']:
        print(f"\nНазвание: {product['name']}")
        print(f"Цена: {product['price']}")
        print(f"Вес: {product['weight']}")
        print("В наличии" if product['available'] else "Нет в наличии!")


def main():
    filename = 'products.json'

    data = load_products(filename)

    display_products(data)

    while True:
        choice = input("\nДобавить новый продукт? (да/нет): ").lower()
        if choice != 'да':
            break
        add_product(data)

    save_products(filename, data)

    print("\nОбновленный список продуктов:")
    display_products(data)


if __name__ == "__main__":
    main()