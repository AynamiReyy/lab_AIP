from random import randint
mass = []
for i in range(5):
    mass.append(randint(0, 10))
for j in range(5):
    a = mass[j]
    mass[j] = "*"
    if a in mass:
        print(a)
        mass[j] = a
        print(mass)