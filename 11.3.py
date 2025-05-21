import csv


def read_and_calculate_expenses(filename):
    try:
        total = 0
        print("Нужно купить:")

        with open(filename, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader)

            for row in reader:
                product, quantity, price = row
                quantity = int(quantity)
                price = int(price)
                total += quantity * price
                print(f"{product} - {quantity} шт. за {price} руб.")

        print(f"Итоговая сумма: {total} руб.")

    except FileNotFoundError:
        print(f"Файл {filename} не найден.")
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")


filename = 'products.csv'
read_and_calculate_expenses(filename)