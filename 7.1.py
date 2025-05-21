from random import randint
mass = []
for i in range(5):
    mass.append(randint(0, 10))

if int(input()) in mass:
    print("Поздравляю, Вы угадали число!", mass)
else:
    print("Нет такого числа!", mass)