def division(num):
    try:
        res = 100 / num
    except ZeroDivisionError:
        res = 0
    return res


while True:
    try:
        num = int(input())
    except ValueError:
        print("Введите число ещё раз")
    else:
        break

print(division(num))
